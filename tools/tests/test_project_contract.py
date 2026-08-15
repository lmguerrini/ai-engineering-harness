"""The contract reader, and the one property that makes it worth having.

Every test here is a falsification attempt against the same claim: that this
reader can never turn "I could not read the declaration" into "the declaration
was empty". That is not a stylistic preference. The defect this whole module
exists to close was a scanner that applied none of its rules and printed
`clean`, and a reader that degrades quietly rebuilds it one layer down.
"""

import json

import pytest

from project_contract import ContractError, ProjectContract, parse_yaml_subset


def test_parses_the_shape_the_contract_template_actually_uses():
    parsed = parse_yaml_subset(
        """
project:
  name: something          # a trailing comment
  repo_path: /tmp/example
  autonomous_integration_merges: true

private_terms:
  project_additions: ["alpha", "beta"]

workspace_classification:
  safe_generated:
    - __pycache__/
    - dist/
  content_exempt: []

capabilities:
  - id: C1
    goal: a thing
    depends_on: []
"""
    )
    assert parsed["project"]["name"] == "something"
    assert parsed["project"]["autonomous_integration_merges"] is True
    assert parsed["private_terms"]["project_additions"] == ["alpha", "beta"]
    assert parsed["workspace_classification"]["safe_generated"] == ["__pycache__/", "dist/"]
    assert parsed["workspace_classification"]["content_exempt"] == []
    assert parsed["capabilities"] == [{"id": "C1", "goal": "a thing", "depends_on": []}]


@pytest.mark.parametrize(
    "document",
    [
        "project:\n  name: a\n   bad_indent: b\n",
        "project:\n\tname: tabbed\n",
        "project:\n  name: 'unterminated\n",
        "project:\n  name: a\nproject:\n  name: b\n",
        "project:\n  terms: [a, [b]]\n",
        "project:\n  terms: [a, b\n",
        "- not a mapping at the top level\n",
    ],
)
def test_every_malformed_document_raises_rather_than_parsing_partially(document):
    """The failure direction that matters.

    A reader returning `{}` here hands a gate an empty rule set, and the gate
    then reports clean over a repository it never checked. Each of these is a
    real shape a hand-edited contract can take.
    """
    with pytest.raises(ContractError):
        parse_yaml_subset(document)


def test_a_duplicate_key_is_refused_rather_than_last_one_winning():
    with pytest.raises(ContractError, match="duplicate key"):
        parse_yaml_subset("private_terms:\n  project_additions: [a]\n  project_additions: [b]\n")


def test_a_hash_inside_a_quoted_scalar_is_data_not_a_comment():
    parsed = parse_yaml_subset('project:\n  pattern: "value # not a comment"\n')
    assert parsed["project"]["pattern"] == "value # not a comment"


def _write_contract(tmp_path, body, *, defaults=None):
    pack = tmp_path / "pack"
    (pack / "policy").mkdir(parents=True)
    (pack / "policy" / "private-terms.default.json").write_text(
        json.dumps(defaults if defaults is not None else {
            "terms": ["runtime pack"], "identity_terms": ["claude"],
            "patterns": [r"\btask[ _-]?id\b"], "identity_patterns": [r"\bphase[ _-]?\d+\b"],
            "optional_patterns": {"ticket_ids": [r"\b[A-Z]{2,4}-\d{1,4}\b"]},
        })
    )
    contract = tmp_path / "PROJECT.yaml"
    contract.write_text(body)
    return contract, pack


def test_project_terms_extend_the_defaults_rather_than_replacing_them(tmp_path):
    """EC-H's core claim, at the layer that decides it."""
    contract, pack = _write_contract(
        tmp_path, "private_terms:\n  project_additions: [\"projectword\"]\n"
    )
    loaded = ProjectContract.load(contract, pack_root=pack)
    assert loaded.default_terms == ("runtime pack",)
    assert loaded.project_terms == ("projectword",)
    assert loaded.default_identity_terms == ("claude",)


def test_a_contract_that_never_names_the_default_set_still_gets_it(tmp_path):
    """Forgetting to name the defaults must not silently disable them."""
    contract, pack = _write_contract(tmp_path, "project:\n  name: x\n")
    loaded = ProjectContract.load(contract, pack_root=pack)
    assert loaded.default_terms == ("runtime pack",)


def test_a_missing_default_term_set_raises_rather_than_scanning_with_nothing(tmp_path):
    contract = tmp_path / "PROJECT.yaml"
    contract.write_text("private_terms:\n  default_set: policy/nowhere.json\n")
    with pytest.raises(ContractError, match="not found"):
        ProjectContract.load(contract, pack_root=tmp_path / "empty")


def test_the_ticket_pattern_is_absent_until_a_project_opts_in(tmp_path):
    """EC-I: the pattern that matched utf-8, SHA-256 and every lockfile entry."""
    contract, pack = _write_contract(tmp_path, "project:\n  name: x\n")
    assert ProjectContract.load(contract, pack_root=pack).project_patterns == ()

    contract2, pack2 = _write_contract(
        tmp_path / "b", "private_terms:\n  optional_pattern_groups: [\"ticket_ids\"]\n"
    )
    opted_in = ProjectContract.load(contract2, pack_root=pack2)
    assert r"\b[A-Z]{2,4}-\d{1,4}\b" in opted_in.project_patterns


def test_opting_into_a_group_that_does_not_exist_is_refused(tmp_path):
    """A typo must not silently enable nothing."""
    contract, pack = _write_contract(
        tmp_path, "private_terms:\n  optional_pattern_groups: [\"tickets\"]\n"
    )
    with pytest.raises(ContractError, match="does not define"):
        ProjectContract.load(contract, pack_root=pack)


def test_a_scalar_where_a_list_belongs_is_refused_with_the_fix_named(tmp_path):
    contract, pack = _write_contract(
        tmp_path, "workspace_classification:\n  content_exempt: annotations/\n"
    )
    with pytest.raises(ContractError, match="must be a list"):
        ProjectContract.load(contract, pack_root=pack)


def test_an_unreadable_contract_raises_rather_than_returning_defaults(tmp_path):
    with pytest.raises(ContractError, match="cannot read"):
        ProjectContract.load(tmp_path / "absent" / "PROJECT.yaml")
