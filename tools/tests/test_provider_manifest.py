"""A provider is a declared manifest; billing safety is a proof about the
exact route, checked before dispatch — never an attribute anyone gets to
assert about a name (D29-D32, D34).

Fixtures use invented names (`vendor-a`, `gateway-a`, `plan-key-a`, …) rather
than a real vendor's, except where a test loads the pack's own shipped
dormant template, which is the one place a real vendor name is authorised to
appear (D34).
"""

import json

import pytest

import provider_manifest as pm
from errors import IntegrityError, PreconditionError

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent.parent
TEMPLATE = ROOT / "templates" / "providers" / "moonshot-kimi-code.dormant.json"


def _surface(**overrides):
    surface = {"surface": "cli-a", "client": "worker-a@gateway-a.example", "protocol": "anthropic-compatible"}
    surface.update(overrides)
    return surface


def _manifest(**overrides):
    document = {
        "schema": "runtime-pack-provider-1",
        "provider_id": "vendor-a-plan",
        "vendor": "vendor-a",
        "gateway": "gateway-a.example",
        "surfaces": [_surface()],
        "adapter": "anthropic-compatible-worker",
        "credential": {
            "kind": "subscription_key",
            "env_file_ref": "VENDOR_A_KEY_FILE",
            "generic_env_forbidden": ["VENDOR_A_API_KEY", "GENERIC_API_KEY"],
        },
        "billing": {
            "billing_mode": "subscription",
            "billing_pool_id": "vendor-a-membership",
            "windows": ["rolling_5h", "weekly"],
            "authorised_by": "decision-a-1",
            "overage_enabled": False,
            "auto_topup_enabled": False,
            "metered_fallback_enabled": False,
        },
        "capacity_observer": {
            "source": "human-reading",
            "freshness_horizon_s": 3600,
            "command": None,
        },
        "discovery": None,
        "private_terms": ["plan-key-a"],
    }
    document.update(overrides)
    return document


def _local_manifest(**overrides):
    """A `local` route: no credential, no observer, needs only its pool."""
    document = _manifest(**overrides)
    document["billing"] = dict(
        document["billing"],
        billing_mode="local",
        billing_pool_id="vendor-a-local-pool",
        authorised_by=None,
        overage_enabled=False,
        auto_topup_enabled=False,
        metered_fallback_enabled=False,
    )
    document["credential"] = dict(document["credential"], env_file_ref=None)
    document["capacity_observer"] = None
    return document


def _write(tmp_path, document, name="manifest.json"):
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _authorised():
    return pm.ProviderManifest.from_mapping(_manifest())


# --- O1 / -k dormant ----------------------------------------------------------


def test_a_dormant_manifest_registers_unchanged_and_is_not_routable():
    manifest = pm.load(TEMPLATE)
    assert manifest.provider_id == "moonshot-kimi-code"
    assert manifest.vendor == "moonshot"
    assert manifest.gateway == "api.kimi.ai"

    fp = pm.fingerprint(manifest, environment={})
    assert fp.authorised_subscription is None
    # The vendor/gateway are read straight from the manifest, never invented.
    assert fp.gateway == "api.kimi.ai"

    verdict = pm.routability(fp, authorised_pools=("moonshot-kimi-code-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_UNAUTHORISED


def test_the_dormant_templates_digest_is_reachable_the_same_way_an_adapters_is():
    digest = pm.manifest_digest(TEMPLATE)
    assert len(digest) == 64
    assert all(character in "0123456789abcdef" for character in digest)


# --- O2 / -k refuse ------------------------------------------------------------


def test_a_manifest_that_is_not_text_is_refused_not_raised(tmp_path):
    """Bytes that are not UTF-8 are a manifest that cannot be read, stated as
    such — the CLI guard in the release suite executes every tool against this
    shape and a traceback is the one answer it refuses."""
    path = tmp_path / "manifest.json"
    path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(pm.IntegrityError):
        pm.load(path)


def test_a_forbidden_name_without_the_metered_suffix_still_poisons_the_route():
    """The manifest's own forbidden list is honoured on its own, independently of
    the suffix heuristic: a name the author forbade is poison even when nothing
    about its shape says so."""
    mapping = _manifest()
    mapping["credential"]["generic_env_forbidden"] = ["VENDOR_A_TOKEN"]
    manifest = pm.ProviderManifest.from_mapping(mapping)
    fp = pm.fingerprint(manifest, environment={"VENDOR_A_TOKEN": "x"})
    assert fp.metered_fallback_enabled is True
    assert pm.routability(fp, authorised_pools=("vendor-a-membership",)).disposition == pm.NOT_ROUTABLE_BILLING


def test_a_null_declaration_in_a_poisoned_environment_is_denied_as_billing_not_unknown():
    """Positive evidence outranks a missing claim: `null` decides the clean case
    only, and a metered name in the environment makes the flag True."""
    mapping = _manifest()
    mapping["billing"]["metered_fallback_enabled"] = None
    manifest = pm.ProviderManifest.from_mapping(mapping)
    fp = pm.fingerprint(manifest, environment={"VENDOR_A_API_KEY": "x"})
    assert fp.metered_fallback_enabled is True
    assert pm.routability(fp, authorised_pools=("vendor-a-membership",)).disposition == pm.NOT_ROUTABLE_BILLING


def test_a_client_config_key_with_a_metered_suffix_is_caught_like_an_environment_name():
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment={}, client_config_keys=("env.VENDOR_A_API_KEY",))
    assert fp.metered_fallback_enabled is True
    fp = pm.fingerprint(manifest, environment={}, client_config_keys=("providers.vendor_a_api_key",))
    assert fp.metered_fallback_enabled is True
    fp = pm.fingerprint(manifest, environment={}, client_config_keys=("a.b.c_env_key",))
    assert fp.metered_fallback_enabled is True


def test_a_repeated_key_is_refused_rather_than_resolved_last_wins(tmp_path):
    text = json.dumps(_manifest())
    # Repeat the whole billing block: the second copy would win under json.loads.
    duplicated = text[:-1] + ', "billing": ' + json.dumps(_manifest()["billing"]) + '}'
    path = tmp_path / "dup.json"
    path.write_text(duplicated)
    with pytest.raises(pm.IntegrityError) as caught:
        pm.load(path)
    assert "repeats a key" in caught.value.cause


# Shapes assembled at runtime so no path literal sits in a tracked file (the outgoing scan reads one as a leak).
@pytest.mark.parametrize("bad", ["x/" + ".." + "/" + ".." + "/y", ".." + "/secret.json", "C:" + "\\x.json", "\\" * 2 + "srv" + "\\" + "sh"])
def test_a_discovery_path_that_escapes_the_project_is_refused(bad):
    mapping = _manifest()
    mapping["discovery"] = bad
    with pytest.raises(pm.IntegrityError):
        pm.ProviderManifest.from_mapping(mapping)


def test_a_wrong_schema_is_refused_for_being_a_wrong_schema():
    with pytest.raises(pm.IntegrityError) as caught:
        pm.ProviderManifest.from_mapping({"schema": "other-schema-1"})
    assert "schema" in caught.value.cause


def test_the_process_environment_flag_reports_a_poisoned_route(monkeypatch, capsys, tmp_path):
    """The flag does something: with a metered-shaped name in the process
    environment the CLI reports the poisoned route, whatever else is ambient."""
    import errors

    path = tmp_path / "m.json"
    path.write_text(json.dumps(_manifest()))
    monkeypatch.setenv("VENDOR_A_API_KEY", "value-that-must-not-print")
    status = errors.run_cli(pm._cli, [str(path), "--environment-from-current-process",
                                      "--authorised-pool", "vendor-a-membership"])
    printed = capsys.readouterr().out
    assert status == 1 and pm.NOT_ROUTABLE_BILLING in printed
    assert "value-that-must-not-print" not in printed


def test_the_credential_file_variable_itself_never_leaks_into_any_output(monkeypatch, capsys, tmp_path):
    """The variable `env_file_ref` NAMES holds a path; neither that path nor the
    file's bytes reach render, repr or the CLI."""
    import errors

    secret_file = tmp_path / "key.txt"
    secret_file.write_text("bytes-that-must-not-print")
    monkeypatch.setenv("VENDOR_A_KEY_FILE", str(secret_file))
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment={"VENDOR_A_KEY_FILE": str(secret_file)})
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    rendered = pm.render(manifest, fp, verdict) + repr(fp) + repr(verdict)
    assert str(secret_file) not in rendered and "bytes-that-must-not-print" not in rendered
    path = tmp_path / "m.json"
    path.write_text(json.dumps(_manifest()))
    errors.run_cli(pm._cli, [str(path), "--environment-from-current-process", "--json"])
    printed = capsys.readouterr().out
    assert str(secret_file) not in printed and "bytes-that-must-not-print" not in printed


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "3600"])
def test_a_freshness_horizon_that_is_not_a_positive_integer_is_refused(bad):
    mapping = _manifest()
    mapping["capacity_observer"]["freshness_horizon_s"] = bad
    with pytest.raises(pm.IntegrityError):
        pm.ProviderManifest.from_mapping(mapping)


def test_a_surface_index_outside_the_declared_surfaces_is_refused():
    manifest = _authorised()
    with pytest.raises(pm.PreconditionError):
        pm.fingerprint(manifest, surface_index=5, environment={})


@pytest.mark.parametrize("key", ["api_key.model", "x.api_key_name", "settings.apikey"])
def test_a_key_that_merely_mentions_a_credential_word_is_not_metered(key):
    assert pm._is_metered_key(key) is False


@pytest.mark.parametrize("path", [("provider_id",), ("gateway",), ("vendor",), ("adapter",),
                                  ("billing", "billing_pool_id"), ("credential", "env_file_ref")])
def test_a_trailing_newline_does_not_slip_past_an_identifier_check(path):
    mapping = _manifest()
    target = mapping
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = str(target[path[-1]]) + "\n"
    with pytest.raises(pm.IntegrityError):
        pm.ProviderManifest.from_mapping(mapping)


def test_a_forbidden_list_entry_with_a_trailing_newline_is_refused():
    mapping = _manifest()
    mapping["credential"]["generic_env_forbidden"] = ["VENDOR_A_TOKEN\n"]
    with pytest.raises(pm.IntegrityError):
        pm.ProviderManifest.from_mapping(mapping)


@pytest.mark.parametrize("path", [("surfaces", 0, "client"), ("billing", "authorised_by"), ("surfaces", 0, "surface")])
def test_a_control_character_in_a_rendered_field_is_refused(path):
    mapping = _manifest()
    target = mapping
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = "x\ndisposition: ROUTABLE"
    with pytest.raises(pm.IntegrityError):
        pm.ProviderManifest.from_mapping(mapping)


def test_render_states_the_flags_as_they_were_established():
    manifest = _authorised()
    clean = pm.fingerprint(manifest, environment={})
    poisoned = pm.fingerprint(manifest, environment={"VENDOR_A_API_KEY": "x"})
    clean_text = pm.render(manifest, clean, pm.routability(clean, authorised_pools=("vendor-a-membership",)))
    poisoned_text = pm.render(manifest, poisoned, pm.routability(poisoned, authorised_pools=("vendor-a-membership",)))
    assert "metered_fallback_enabled=false" in clean_text
    assert "metered_fallback_enabled=true" in poisoned_text
    unknown = pm.fingerprint(manifest, environment=None)
    unknown_text = pm.render(manifest, unknown, pm.routability(unknown, authorised_pools=("vendor-a-membership",)))
    assert "not established" in unknown_text
    assert "metered_fallback_enabled=UNKNOWN" in unknown_text


def test_the_json_output_carries_the_reasons(tmp_path, capsys):
    import errors

    path = tmp_path / "m.json"
    path.write_text(json.dumps(_manifest()))
    errors.run_cli(pm._cli, [str(path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["reasons"] and isinstance(payload["reasons"], list)


def test_a_huge_integer_literal_is_refused_not_raised(tmp_path):
    path = tmp_path / "big.json"
    path.write_text('{"schema": "runtime-pack-provider-1", "n": ' + "9" * 5000 + "}")
    with pytest.raises(pm.IntegrityError):
        pm.load(path)


def test_a_wrong_schema_wins_over_a_foreign_key():
    with pytest.raises(pm.IntegrityError) as caught:
        pm.ProviderManifest.from_mapping({"schema": "other-schema-1", "foreign": 1})
    assert "schema" in caught.value.cause


def test_a_non_string_credential_reference_is_not_echoed():
    mapping = _manifest()
    mapping["credential"]["env_file_ref"] = ["value-that-must-not-print"]
    with pytest.raises(pm.IntegrityError) as caught:
        pm.ProviderManifest.from_mapping(mapping)
    assert "value-that-must-not-print" not in caught.value.render()


def test_a_forbidden_list_entry_that_is_not_a_variable_name_is_refused():
    mapping = _manifest()
    mapping["credential"]["generic_env_forbidden"] = ["a b"]
    with pytest.raises(pm.IntegrityError):
        pm.ProviderManifest.from_mapping(mapping)


def test_a_document_nested_beyond_reason_is_refused_not_raised(tmp_path):
    path = tmp_path / "deep.json"
    path.write_text("[" * 100000)
    with pytest.raises(pm.IntegrityError):
        pm.load(path)


def test_the_env_file_ref_refusal_does_not_echo_the_offending_text():
    mapping = _manifest()
    mapping["credential"]["env_file_ref"] = "sk-" + "value-that-must-not-print"
    with pytest.raises(pm.IntegrityError) as caught:
        pm.ProviderManifest.from_mapping(mapping)
    assert "value-that-must-not-print" not in caught.value.render()


def test_a_metered_client_key_denies_even_without_an_environment():
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment=None, client_config_keys=("model.default.api_key",))
    assert fp.metered_fallback_enabled is True


def test_a_deeply_nested_object_value_is_refused_not_raised():
    """A value nested deep enough to overflow `repr` must be refused by a message
    that never tries to print it — the refusal itself was the traceback."""
    deep: dict = {}
    cursor = deep
    for _ in range(18000):
        cursor["a"] = {}
        cursor = cursor["a"]
    mapping = _manifest()
    mapping["billing"]["windows"] = deep
    with pytest.raises(pm.IntegrityError):
        pm.ProviderManifest.from_mapping(mapping)


def test_a_document_nested_past_the_reader_bound_is_refused_at_load(tmp_path):
    path = tmp_path / "deep.json"
    path.write_text('{"schema": "runtime-pack-provider-1", "x": ' + "[" * 40 + "]" * 40 + "}")
    with pytest.raises(pm.IntegrityError) as caught:
        pm.load(path)
    assert "nested beyond" in caught.value.cause


def test_a_prepaid_route_without_an_authorising_decision_is_not_routable():
    document = _manifest()
    document["billing"] = dict(document["billing"], billing_mode="prepaid_existing", authorised_by=None)
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={})
    assert pm.routability(fp, authorised_pools=("vendor-a-membership",)).disposition == pm.NOT_ROUTABLE_UNAUTHORISED


@pytest.mark.parametrize("bad", ["c@x\u0085disposition: ROUTABLE", "c@x\u2028x", "c@x\u2029x"])
def test_a_unicode_line_separator_in_a_rendered_field_is_refused(bad):
    mapping = _manifest()
    mapping["surfaces"][0]["client"] = bad
    with pytest.raises(pm.IntegrityError):
        pm.ProviderManifest.from_mapping(mapping)


def test_the_unknown_sentinel_is_not_an_authorising_decision():
    mapping = _manifest()
    mapping["billing"]["authorised_by"] = "UNKNOWN"
    with pytest.raises(pm.IntegrityError):
        pm.ProviderManifest.from_mapping(mapping)


@pytest.mark.parametrize("path", [("credential", "generic_env_forbidden"), ("credential", "kind"), ("billing", "windows")])
def test_a_refusal_never_echoes_the_offending_content(path):
    mapping = _manifest()
    target = mapping
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = "value-that-must-not-print"
    with pytest.raises(pm.IntegrityError) as caught:
        pm.ProviderManifest.from_mapping(mapping)
    assert "value-that-must-not-print" not in caught.value.render()


def test_an_unknown_key_that_is_unprintable_or_huge_is_described_not_echoed():
    mapping = _manifest()
    mapping["x" * 200] = 1
    with pytest.raises(pm.IntegrityError) as caught:
        pm.ProviderManifest.from_mapping(mapping)
    assert "x" * 100 not in caught.value.render() and "<200 characters>" in caught.value.render()
    mapping = _manifest()
    mapping["k\ndisposition: ROUTABLE"] = 1
    with pytest.raises(pm.IntegrityError) as caught:
        pm.ProviderManifest.from_mapping(mapping)
    assert "disposition: ROUTABLE" not in caught.value.render()


def test_a_repeated_unprintable_key_is_described_not_echoed(tmp_path):
    path = tmp_path / "dup.json"
    path.write_text('{"schema": "runtime-pack-provider-1", "a\\nb": 1, "a\\nb": 2}')
    with pytest.raises(pm.IntegrityError) as caught:
        pm.load(path)
    assert "\n" not in caught.value.render().split("key:")[-1].strip()


def test_a_numeric_value_in_a_refusal_is_named_by_type():
    mapping = _manifest()
    mapping["billing"]["authorised_by"] = 12345678901234567890
    with pytest.raises(pm.IntegrityError) as caught:
        pm.ProviderManifest.from_mapping(mapping)
    assert "12345678901234567890" not in caught.value.render()


def test_an_unknown_top_level_key_is_refused(tmp_path):
    with pytest.raises(IntegrityError, match="does not implement"):
        pm.ProviderManifest.from_mapping(_manifest(isolation="worktree"))


def test_an_unknown_nested_key_is_refused(tmp_path):
    document = _manifest()
    document["billing"] = dict(document["billing"], extra_field="nope")
    with pytest.raises(IntegrityError, match="does not implement"):
        pm.ProviderManifest.from_mapping(document)


def test_an_unknown_key_inside_a_surface_is_refused():
    document = _manifest(surfaces=[_surface(extra_field="nope")])
    with pytest.raises(IntegrityError, match="does not implement"):
        pm.ProviderManifest.from_mapping(document)


def test_an_unknown_key_inside_credential_is_refused():
    document = _manifest()
    document["credential"] = dict(document["credential"], extra_field="nope")
    with pytest.raises(IntegrityError, match="does not implement"):
        pm.ProviderManifest.from_mapping(document)


def test_an_unknown_key_inside_capacity_observer_is_refused():
    document = _manifest()
    document["capacity_observer"] = dict(document["capacity_observer"], extra_field="nope")
    with pytest.raises(IntegrityError, match="does not implement"):
        pm.ProviderManifest.from_mapping(document)


def test_a_protocol_outside_the_vocabulary_is_refused_citing_D31(tmp_path):
    document = _manifest(surfaces=[_surface(protocol="native-cli")])
    with pytest.raises(IntegrityError) as caught:
        pm.ProviderManifest.from_mapping(document)
    assert "D31" in caught.value.cause


def test_a_billing_mode_outside_the_vocabulary_is_refused(tmp_path):
    document = _manifest()
    document["billing"] = dict(document["billing"], billing_mode="crypto")
    with pytest.raises(IntegrityError, match="billing_mode"):
        pm.ProviderManifest.from_mapping(document)


def test_a_window_outside_the_vocabulary_is_refused():
    document = _manifest()
    document["billing"] = dict(document["billing"], windows=["daily"])
    with pytest.raises(IntegrityError, match="window"):
        pm.ProviderManifest.from_mapping(document)


def test_an_observer_source_outside_the_vocabulary_is_refused():
    document = _manifest()
    document["capacity_observer"] = dict(document["capacity_observer"], source="carrier-pigeon")
    with pytest.raises(IntegrityError, match="capacity_observer.source"):
        pm.ProviderManifest.from_mapping(document)


def test_a_credential_kind_outside_the_vocabulary_is_refused():
    document = _manifest()
    document["credential"] = dict(document["credential"], kind="anonymous")
    with pytest.raises(IntegrityError, match="credential.kind"):
        pm.ProviderManifest.from_mapping(document)


def test_a_schema_mismatch_on_an_otherwise_complete_document_is_refused():
    document = _manifest(schema="runtime-pack-provider-2")
    with pytest.raises(IntegrityError, match="schema"):
        pm.ProviderManifest.from_mapping(document)


def test_a_non_bool_flag_is_refused():
    document = _manifest()
    document["billing"] = dict(document["billing"], overage_enabled="yes")
    with pytest.raises(IntegrityError, match="overage_enabled"):
        pm.ProviderManifest.from_mapping(document)


def test_billing_pool_id_equal_to_provider_id_is_refused(tmp_path):
    document = _manifest()
    document["billing"] = dict(document["billing"], billing_pool_id=document["provider_id"])
    with pytest.raises(IntegrityError, match="differ from provider_id"):
        pm.ProviderManifest.from_mapping(document)


def test_empty_surfaces_is_refused(tmp_path):
    with pytest.raises(IntegrityError):
        pm.ProviderManifest.from_mapping(_manifest(surfaces=[]))


def test_a_gateway_with_a_scheme_is_refused(tmp_path):
    with pytest.raises(IntegrityError):
        pm.ProviderManifest.from_mapping(_manifest(gateway="https://gateway-a.example"))


def test_a_gateway_with_a_path_and_no_scheme_is_refused():
    with pytest.raises(IntegrityError):
        pm.ProviderManifest.from_mapping(_manifest(gateway="gateway-a.example/api"))


def test_invalid_json_is_refused(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(IntegrityError, match="not valid JSON"):
        pm.load(path)


def test_an_unreadable_path_is_refused(tmp_path):
    with pytest.raises(IntegrityError, match="cannot be read"):
        pm.load(tmp_path / "does-not-exist.json")


def test_an_env_file_ref_that_looks_like_a_value_is_refused(tmp_path):
    document = _manifest()
    for bad in ("secrets/key.txt", "NAME=value"):
        broken = dict(document)
        broken["credential"] = dict(document["credential"], env_file_ref=bad)
        with pytest.raises(IntegrityError, match="path or the value itself"):
            pm.ProviderManifest.from_mapping(broken)


@pytest.mark.parametrize("bad_name", ["C:\\keys\\k.txt", "~keyfile", "MY KEY", "key.txt"])
def test_an_env_file_ref_not_shaped_like_an_identifier_is_refused(bad_name):
    """`env_file_ref` is validated as an environment-variable NAME
    (`^[A-Za-z_][A-Za-z0-9_]*$`), not merely "not a path"."""
    document = _manifest()
    document["credential"] = dict(document["credential"], env_file_ref=bad_name)
    with pytest.raises(IntegrityError):
        pm.ProviderManifest.from_mapping(document)


@pytest.mark.parametrize("bad_id", ["Vendor-A", "vendor_a", "-vendor-a", "", "vendor a"])
def test_a_non_slug_provider_id_is_refused(bad_id):
    with pytest.raises(IntegrityError):
        pm.ProviderManifest.from_mapping(_manifest(provider_id=bad_id))


def test_a_non_mapping_manifest_is_refused():
    with pytest.raises(IntegrityError):
        pm.ProviderManifest.from_mapping(["not", "a", "mapping"])


@pytest.mark.parametrize("bad_value", ["", "   "])
def test_authorised_by_empty_or_whitespace_is_refused(bad_value):
    """An empty or whitespace-only `authorised_by` reached ROUTABLE while
    the render printed `authorised_by=UNKNOWN` — refused at validation, the
    same rule every other string field in this schema uses."""
    document = _manifest()
    document["billing"] = dict(document["billing"], authorised_by=bad_value)
    with pytest.raises(IntegrityError, match="authorised_by"):
        pm.ProviderManifest.from_mapping(document)


# Built at runtime so that no absolute path is present as a literal in a tracked file:
# the pack's own outgoing scan reads one as a leak, and the property under test is
# the refusal, not the spelling.
@pytest.mark.parametrize("bad_path", ["/" + "etc/discovery.json", "~" + "/discovery.json"])
def test_an_absolute_or_home_relative_discovery_path_is_refused(bad_path):
    with pytest.raises(IntegrityError, match="discovery"):
        pm.ProviderManifest.from_mapping(_manifest(discovery=bad_path))


def test_a_relative_discovery_path_is_accepted():
    manifest = pm.ProviderManifest.from_mapping(_manifest(discovery="discovery/catalogue.json"))
    assert manifest.discovery == "discovery/catalogue.json"


# --- O5 / -k poisoned -----------------------------------------------------------


def test_an_authorised_subscription_manifest_is_routable_with_a_clean_environment():
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment={})
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.ROUTABLE


def test_a_poisoned_forbidden_variable_present_makes_the_same_manifest_not_routable_billing():
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment={"VENDOR_A_API_KEY": "poisoned-value"})
    assert fp.metered_fallback_enabled is True
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_BILLING


def test_a_manifest_that_declares_a_metered_fallback_is_poisoned_by_its_own_word():
    """No environment can make a route cleaner than its manifest admits: a
    declared `metered_fallback_enabled: true` is established from the manifest
    and denied even against the cleanest environment."""
    mapping = _manifest()
    mapping["billing"]["metered_fallback_enabled"] = True
    manifest = pm.ProviderManifest.from_mapping(mapping)
    fp = pm.fingerprint(manifest, environment={})
    assert fp.metered_fallback_enabled is True
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_BILLING


def test_no_environment_value_string_ever_appears_in_the_fingerprint_repr():
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment={"VENDOR_A_API_KEY": "super-secret-value"})
    assert "super-secret-value" not in repr(fp)


def test_environment_none_is_unknown_not_clean():
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment=None)
    assert fp.metered_fallback_enabled == pm.UNKNOWN
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_UNKNOWN


def test_a_client_config_key_naming_a_metered_credential_is_not_routable_billing():
    manifest = _authorised()
    fp = pm.fingerprint(
        manifest, environment={}, client_config_keys=("model.default.api_key",)
    )
    assert fp.metered_fallback_enabled is True
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_BILLING


def test_a_metered_manifest_stays_not_routable_billing_with_the_cleanest_environment():
    document = _manifest()
    document["billing"] = dict(
        document["billing"],
        billing_mode="metered_api",
        overage_enabled=False,
        auto_topup_enabled=False,
        metered_fallback_enabled=False,
    )
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={})
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_BILLING


def test_a_poisoned_paygo_credential_never_makes_an_unauthorised_manifest_routable():
    document = _manifest()
    document["billing"] = dict(document["billing"], authorised_by=None)
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={"VENDOR_A_API_KEY": "x"})
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_UNAUTHORISED


def test_a_missing_env_file_ref_is_not_routable_credential_even_unpoisoned():
    document = _manifest()
    document["credential"] = dict(document["credential"], env_file_ref=None)
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={})
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_CREDENTIAL


def test_flags_null_is_not_routable_unknown():
    document = _manifest()
    document["billing"] = dict(
        document["billing"], overage_enabled=None, auto_topup_enabled=None, metered_fallback_enabled=None
    )
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={})
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_UNKNOWN


@pytest.mark.parametrize("null_flag", ["overage_enabled", "auto_topup_enabled", "metered_fallback_enabled"])
def test_each_flag_null_alone_is_not_routable_unknown(null_flag):
    """Each flag, on its own, with the other two declared `false`, a clean
    environment and an authorised pool, still hard-denies as UNKNOWN."""
    document = _manifest()
    flags = {"overage_enabled": False, "auto_topup_enabled": False, "metered_fallback_enabled": False}
    flags[null_flag] = None
    document["billing"] = dict(document["billing"], **flags)
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={})
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_UNKNOWN


def test_metered_fallback_false_with_a_clean_inspected_environment_is_routable():
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment={})
    assert fp.metered_fallback_enabled is False
    assert pm.routability(fp, authorised_pools=("vendor-a-membership",)).disposition == pm.ROUTABLE


def test_metered_fallback_false_with_no_environment_is_not_routable_unknown():
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment=None)
    assert fp.metered_fallback_enabled == pm.UNKNOWN
    assert pm.routability(fp, authorised_pools=("vendor-a-membership",)).disposition == pm.NOT_ROUTABLE_UNKNOWN


def test_an_environment_name_shaped_like_a_metered_credential_poisons_even_when_undeclared():
    """A name ending in `_API_KEY`/`_ENV_KEY` (case-insensitive) poisons the
    route whether or not the manifest's own `generic_env_forbidden` names it."""
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment={"some_other_env_key": "x"})
    assert fp.metered_fallback_enabled is True
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_BILLING


def test_an_empty_generic_env_forbidden_list_is_unknown_even_with_a_clean_environment():
    """Nothing was declared to look for, so a clean read is not the same
    claim as a checked one."""
    document = _manifest()
    document["credential"] = dict(document["credential"], generic_env_forbidden=[])
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={})
    assert fp.metered_fallback_enabled == pm.UNKNOWN
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_UNKNOWN


def test_is_metered_key_case_folds_the_last_segment():
    """The last segment is case-folded and matched by suffix."""
    assert pm._is_metered_key("API_KEY") is True
    assert pm._is_metered_key("model.API_KEY") is True
    assert pm._is_metered_key("model.default.api_key") is True
    assert pm._is_metered_key("model.apikey") is False


# --- authorised_by set, credential set, flags false, pool absent -----------


def test_a_subscription_manifest_with_the_pool_absent_from_authorised_pools_is_not_routable_unauthorised():
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment={})
    verdict = pm.routability(fp, authorised_pools=())
    assert verdict.disposition == pm.NOT_ROUTABLE_UNAUTHORISED


# --- no capacity observer configured ---------------------------------------


def test_a_subscription_manifest_with_no_capacity_observer_is_not_routable_unknown():
    document = _manifest()
    document["capacity_observer"] = None
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={})
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_UNKNOWN
    assert any("capacity_observer is null" in reason for reason in verdict.reasons)


def test_the_dormant_templates_verdict_is_unchanged_by_the_observer_check():
    """The template carries an observer, so this check never fires for it; its
    verdict stays the one the subscription-authorisation check already gives."""
    manifest = pm.load(TEMPLATE)
    fp = pm.fingerprint(manifest, environment={})
    assert fp.capacity_observer_configured is True
    verdict = pm.routability(fp, authorised_pools=("moonshot-kimi-code-membership",))
    assert verdict.disposition == pm.NOT_ROUTABLE_UNAUTHORISED


# --- local and prepaid_existing dispositions --------------------------------


def test_local_mode_is_routable_when_its_pool_is_authorised():
    manifest = pm.ProviderManifest.from_mapping(_local_manifest())
    fp = pm.fingerprint(manifest, environment=None)
    verdict = pm.routability(fp, authorised_pools=("vendor-a-local-pool",))
    assert verdict.disposition == pm.ROUTABLE


def test_local_mode_is_not_routable_unauthorised_when_its_pool_is_absent():
    manifest = pm.ProviderManifest.from_mapping(_local_manifest())
    fp = pm.fingerprint(manifest, environment=None)
    verdict = pm.routability(fp, authorised_pools=())
    assert verdict.disposition == pm.NOT_ROUTABLE_UNAUTHORISED


def test_prepaid_existing_is_not_routable_unauthorised_when_its_pool_is_absent():
    document = _manifest()
    document["billing"] = dict(document["billing"], billing_mode="prepaid_existing", authorised_by="decision-p")
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={})
    verdict = pm.routability(fp, authorised_pools=())
    assert verdict.disposition == pm.NOT_ROUTABLE_UNAUTHORISED


def test_prepaid_existing_is_routable_when_its_pool_is_present_with_credential_and_clean_flags():
    document = _manifest()
    document["billing"] = dict(document["billing"], billing_mode="prepaid_existing", authorised_by="decision-p")
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={})
    verdict = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert verdict.disposition == pm.ROUTABLE


# --- a live flag denies `local` exactly as it does every other mode --------


def test_local_mode_with_a_self_declared_true_flag_is_not_routable_billing():
    document = _local_manifest()
    document["billing"] = dict(document["billing"], overage_enabled=True)
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment=None)
    verdict = pm.routability(fp, authorised_pools=("vendor-a-local-pool",))
    assert verdict.disposition == pm.NOT_ROUTABLE_BILLING


def test_local_mode_with_a_poisoned_inspected_environment_is_not_routable_billing():
    document = _local_manifest()
    document["credential"] = dict(
        document["credential"], generic_env_forbidden=["VENDOR_A_API_KEY"]
    )
    manifest = pm.ProviderManifest.from_mapping(document)
    fp = pm.fingerprint(manifest, environment={"VENDOR_A_API_KEY": "poisoned-value"})
    assert fp.metered_fallback_enabled is True
    verdict = pm.routability(fp, authorised_pools=("vendor-a-local-pool",))
    assert verdict.disposition == pm.NOT_ROUTABLE_BILLING


def test_local_mode_with_unknown_flags_stays_routable():
    """UNKNOWN flags are irrelevant for `local`: no billing pool is overrun by
    an unestablished fact."""
    manifest = pm.ProviderManifest.from_mapping(_local_manifest())
    fp = pm.fingerprint(manifest, environment=None)
    assert fp.metered_fallback_enabled == pm.UNKNOWN
    verdict = pm.routability(fp, authorised_pools=("vendor-a-local-pool",))
    assert verdict.disposition == pm.ROUTABLE


# --- O12 / -k mutation -----------------------------------------------------------


def test_mutation_of_flag_is_false_to_always_pass_flips_the_poisoned_oracle(monkeypatch):
    """Without the guard, a live `True` metered flag would read as cleared."""
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment={"VENDOR_A_API_KEY": "poisoned-value"})
    assert pm.routability(fp, authorised_pools=("vendor-a-membership",)).disposition == pm.NOT_ROUTABLE_BILLING

    monkeypatch.setattr(pm, "_flag_is_false", lambda value: True)
    mutated = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    with pytest.raises(AssertionError):
        assert mutated.disposition == pm.NOT_ROUTABLE_BILLING


def test_mutation_pooling_an_unknown_flag_as_false_is_caught():
    """The one mutation D29's own wording warns about: reading UNKNOWN as
    cleared rather than as hard deny."""
    manifest = _authorised()
    fp = pm.fingerprint(manifest, environment=None)  # metered_fallback_enabled UNKNOWN
    honest = pm.routability(fp, authorised_pools=("vendor-a-membership",))
    assert honest.disposition == pm.NOT_ROUTABLE_UNKNOWN

    def _pools_unknown_as_false(value):
        return value is False or value == pm.UNKNOWN

    import provider_manifest as target
    original = target._flag_is_false
    target._flag_is_false = _pools_unknown_as_false
    try:
        mutated = target.routability(fp, authorised_pools=("vendor-a-membership",))
        with pytest.raises(AssertionError):
            assert mutated.disposition == pm.NOT_ROUTABLE_UNKNOWN
    finally:
        target._flag_is_false = original


# --- vocabulary guard ------------------------------------------------------------


def test_protocols_is_exactly_the_two_this_release_supports():
    """D31: adding a protocol is a Core change, not a manifest value. Pinned so
    a third entry lands here deliberately rather than by a quiet edit."""
    assert pm.PROTOCOLS == ("anthropic-compatible", "openai-compatible")


# --- CLI ---------------------------------------------------------------------


def test_cli_exits_0_on_a_routable_manifest(tmp_path, capsys):
    """A `local` manifest needs neither a credential nor an inspected
    environment, so this is deterministic without touching the real process
    environment at all — see `_local_manifest`."""
    path = _write(tmp_path, _local_manifest())
    status = pm._cli([str(path), "--authorised-pool", "vendor-a-local-pool"])
    assert status == 0
    assert "ROUTABLE" in capsys.readouterr().out


def test_cli_exits_1_on_a_not_routable_manifest(tmp_path, capsys):
    path = _write(tmp_path, json.loads(TEMPLATE.read_text(encoding="utf-8")))
    status = pm._cli([str(path)])
    assert status == 1
    assert "NOT_ROUTABLE_UNAUTHORISED" in capsys.readouterr().out


def test_cli_exits_2_via_run_cli_on_a_refusal(capsys, tmp_path):
    import errors

    status = errors.run_cli(pm._cli, [str(tmp_path / "no-such-manifest.json")])
    assert status == 2
    printed = capsys.readouterr().out
    assert printed.startswith("REFUSED HX_")


def test_help_exits_via_system_exit_and_touches_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        pm._cli(["--help"])
    assert list(tmp_path.iterdir()) == []


def test_environment_from_current_process_never_prints_a_value(tmp_path, monkeypatch, capsys):
    """The sole CLI test exercising `--environment-from-current-process`, and
    only for this one property: any real ambient variable shaped like
    a metered credential makes the disposition itself nondeterministic in
    this environment, so nothing here asserts one."""
    monkeypatch.setenv("VENDOR_A_API_KEY", "should-never-print")
    path = _write(tmp_path, _manifest())
    pm._cli([str(path), "--environment-from-current-process", "--authorised-pool", "vendor-a-membership"])
    printed = capsys.readouterr().out
    assert "should-never-print" not in printed
