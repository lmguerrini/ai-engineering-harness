"""The contract reader, and the one property that makes it worth having.

Every test here is a falsification attempt against the same claim: that this
reader can never turn "I could not read the declaration" into "the declaration
was empty". That is not a stylistic preference. The defect this whole module
exists to close was a scanner that applied none of its rules and printed
`clean`, and a reader that degrades quietly rebuilds it one layer down.
"""

import json

import pytest

from pathlib import Path

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


# --- CA-AMD-6: valid multi-line data was refused -----------------------------
#
# Reproduced against frozen 2.1.1: `|`, `>`, `|-`, `|+` and a flow sequence
# spanning lines every one raised `line N: unexpected indentation`. Fail-closed,
# which is the right direction and still a defect — D10 makes PROJECT.yaml the
# single source for every gate, so a project that needs a multi-line value in it
# cannot use the gates at all.
#
# The expectations below were produced by differential comparison against a
# reference YAML implementation over the full cross-product of style, chomping
# indicator and body shape (60 cases, zero divergences). That library is an
# oracle used during development and is deliberately NOT imported here: the
# toolbelt is import-closed (D3), and a test that needs an installed package to
# run is a test that stops running exactly where the tool is most needed.


@pytest.mark.parametrize(
    "document, expected",
    [
        # literal: line breaks are kept
        ("a:\n  n: |\n    x\n    y\n", "x\ny\n"),
        # folded: a single break between content lines becomes a space
        ("a:\n  n: >\n    x\n    y\n", "x y\n"),
        # strip: no trailing break
        ("a:\n  n: |-\n    x\n    y\n", "x\ny"),
        ("a:\n  n: >-\n    x\n    y\n", "x y"),
        # keep: every trailing break survives
        ("a:\n  n: |+\n    x\n\n  m: 1\n", "x\n\n"),
        # clip (the default): trailing breaks collapse to exactly one
        ("a:\n  n: |\n    x\n\n\n  m: 1\n", "x\n"),
        # a blank line BETWEEN content lines is content
        ("a:\n  n: |\n    x\n\n    y\n", "x\n\ny\n"),
        ("a:\n  n: >\n    x\n\n    y\n", "x\ny\n"),
        # indentation inside the block is data
        ("a:\n  n: |\n    x\n      deeper\n    y\n", "x\n  deeper\ny\n"),
        # so is a `#`, a `:` and a `-`
        ("a:\n  n: |\n    # not a comment\n", "# not a comment\n"),
        ("a:\n  n: |\n    key: value\n", "key: value\n"),
        ("a:\n  n: |\n    - not a list item\n", "- not a list item\n"),
        # an empty block is the empty string, which is a value
        ("a:\n  n: |\n  m: 1\n", ""),
    ],
)
def test_a_block_scalar_parses(document, expected):
    assert parse_yaml_subset(document)["a"]["n"] == expected


def test_a_block_scalar_does_not_swallow_the_next_key():
    assert parse_yaml_subset("a:\n  n: |\n    x\n  m: 2\n") == {"a": {"n": "x\n", "m": 2}}


def test_a_block_scalar_does_not_swallow_a_dedented_key():
    assert parse_yaml_subset("a:\n  n: |\n    x\nb: 2\n") == {"a": {"n": "x\n"}, "b": 2}


def test_a_block_scalar_works_inside_a_sequence_item():
    parsed = parse_yaml_subset("a:\n  - id: 1\n    note: |\n      x\n      y\n")
    assert parsed == {"a": [{"id": 1, "note": "x\ny\n"}]}


def test_a_flow_sequence_may_span_lines():
    assert parse_yaml_subset("a:\n  n: [x,\n      y]\n") == {"a": {"n": ["x", "y"]}}
    assert parse_yaml_subset("a:\n  n: [x,\n   y,\n   z]\n") == {"a": {"n": ["x", "y", "z"]}}


def test_an_unterminated_flow_sequence_still_raises():
    with pytest.raises(ContractError):
        parse_yaml_subset("a:\n  n: [x,\n      y\nb: 2\n")


def test_an_explicit_block_indentation_indicator_is_refused_by_name():
    """Rare, and a scalar that is *nearly* right is worse here than a refusal."""
    with pytest.raises(ContractError) as caught:
        parse_yaml_subset("a:\n  n: |2\n    x\n")
    assert "indentation indicator" in str(caught.value)


def test_a_plain_scalar_continued_across_lines_is_refused_with_the_remedy():
    """Still refused, because it cannot be told apart from an indentation typo
    — but the refusal now names the construct that does work."""
    with pytest.raises(ContractError) as caught:
        parse_yaml_subset("a:\n  n: x\n    y\n")
    assert "block scalar" in str(caught.value)


def test_a_genuine_indentation_typo_is_still_refused():
    with pytest.raises(ContractError):
        parse_yaml_subset("a:\n  n: 1\n     oops: 2\n")


def test_a_block_scalar_opened_on_a_sequence_item_line_parses():
    """`- goal: |` — the block header on the dash line. `_KEY` never matches a
    `- ` line, so the header was invisible and the refusal told the author to
    write the very form they had written. Found by an independent audit."""
    parsed = parse_yaml_subset(
        "capabilities:\n  - goal: |\n      do the thing\n      carefully\n    id: C1\n"
    )
    assert parsed == {"capabilities": [{"goal": "do the thing\ncarefully\n", "id": "C1"}]}


def test_a_block_on_a_sequence_item_line_does_not_swallow_the_item_s_other_keys():
    parsed = parse_yaml_subset("c:\n  - note: |\n      a\n    id: 1\n    k: v\n")
    assert parsed == {"c": [{"note": "a\n", "id": 1, "k": "v"}]}


def test_consecutive_sequence_items_may_each_open_a_block():
    parsed = parse_yaml_subset("c:\n  - goal: |\n      one\n  - goal: |\n      two\n")
    assert parsed == {"c": [{"goal": "one\n"}, {"goal": "two\n"}]}


def test_a_keep_chomped_block_with_an_all_blank_body_keeps_its_newlines():
    assert parse_yaml_subset("a:\n  n: |+\n\n  m: 1\n") == {"a": {"n": "\n", "m": 1}}


@pytest.mark.parametrize("document", ["a: &anchor 1\n", "a: 1\nb: *anchor\n"])
def test_anchors_and_aliases_are_refused_rather_than_guessed(document):
    """`a: &x 1` parsed to the string `'&x 1'` — a value nobody wrote, in a
    module that promises to raise rather than guess."""
    with pytest.raises(ContractError) as caught:
        parse_yaml_subset(document)
    assert "anchors and aliases" in str(caught.value)


def test_a_doubled_quote_inside_a_single_quoted_scalar_is_one_quote():
    assert parse_yaml_subset("t: 'it''s'\n") == {"t": "it's"}
    assert parse_yaml_subset('t: "it""s"\n') == {"t": 'it""s'}


# --- which copy of the rule actually ran --------------------------------------
#
# Reproduced against the frozen 2.2.0 baseline: a project declaring a pack root
# whose default term set is not present under it silently got a copy sitting
# beside its own contract, applied that copy's terms, and reported only how many
# terms there were. Nine refusals against a rule that yields one is the measured
# cost of the same shape elsewhere.


def _contract_with_a_copy_beside_it(tmp_path, *, term):
    (tmp_path / "pack").mkdir()
    (tmp_path / "private-terms.default.json").write_text(
        '{"policy_schema": 2, "terms": ["%s"], "identity_terms": [], "patterns": [],'
        ' "identity_patterns": [], "optional_patterns": {}}' % term,
        encoding="utf-8",
    )
    contract = tmp_path / "PROJECT.yaml"
    contract.write_text(
        "project:\n  name: rule-source\n  repo_path: .\n"
        "private_terms:\n  default_set: private-terms.default.json\n",
        encoding="utf-8",
    )
    return contract


def test_a_rule_resolved_outside_the_declared_pack_root_is_refused(tmp_path):
    contract = _contract_with_a_copy_beside_it(tmp_path, term="ghost term")
    with pytest.raises(ContractError) as caught:
        ProjectContract.load(contract, pack_root=tmp_path / "pack")
    message = str(caught.value)
    assert "cache rather than an authority" in message
    assert str(tmp_path / "pack") in message, "the refusal must name the root it measured against"
    assert "private-terms.default.json" in message


def test_the_refusal_names_every_location_it_looked_in(tmp_path):
    """After a surprising finding count the first question is which copy ran,
    and the second is what else was on the path."""
    contract = _contract_with_a_copy_beside_it(tmp_path, term="ghost term")
    with pytest.raises(ContractError) as caught:
        ProjectContract.load(contract, pack_root=tmp_path / "pack")
    assert str((tmp_path / "pack" / "private-terms.default.json")) in str(caught.value)


def test_a_contract_records_where_it_read_its_vocabulary_from(tmp_path):
    """The disclosure half. Refusing the substitution is not enough on its own:
    a report that does not say which file it applied cannot be audited."""
    contract = _contract_with_a_copy_beside_it(tmp_path, term="declared term")
    loaded = ProjectContract.load(contract, pack_root=tmp_path)
    assert "declared term" in loaded.default_terms
    source = loaded.default_terms_source
    assert source is not None, "a contract that cannot say where its rule came from is the defect"
    assert source.canonical and source.how == "canonical"
    assert len(source.digest) == 64
    assert "private-terms.default.json" in source.summary()


# --- a declared repository is the PROJECT's, not the process's --------------------


def _contract_at(root, repo_path='"."'):
    root.mkdir(parents=True, exist_ok=True)
    (root / "PROJECT.yaml").write_text(
        "project:\n  name: p\n"
        f"  repo_path: {repo_path}\n"
        'pack:\n  root_path: "/nowhere"\n'
        "capabilities:\n  - id: C1\n", encoding="utf-8")
    return root / "PROJECT.yaml"


def test_a_relative_repository_resolves_against_the_project_not_the_process(tmp_path, monkeypatch):
    """`repo_path: "."` is what every rehearsal fixture in this pack declares,
    and any project may declare a relative path.

    REPRODUCED BEFORE THE REPAIR: it returned the literal `"."`, so every CLI
    that falls back to it — the commit gate over a range, the outgoing scan, the
    workspace report, the publication gate — ran against whatever repository the
    invoking shell happened to be in. Two projects on one machine got the same
    answer, and it was the answer for neither of them.
    """
    project = tmp_path / "a-project"
    contract = ProjectContract.load(_contract_at(project))

    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    resolved = Path(contract.repository())
    assert resolved.is_absolute(), (
        f"repository() returned {resolved!s}, which is relative — so it names whatever "
        f"directory the caller is standing in"
    )
    assert resolved == project.resolve(), (
        f"repository() resolved to {resolved} from a working directory of {elsewhere}; "
        f"the contract lives in {project}"
    )


def test_two_projects_declaring_the_same_relative_path_are_two_repositories(tmp_path):
    """The failure as a reader meets it: one number, shown twice, for two projects."""
    one = ProjectContract.load(_contract_at(tmp_path / "one"))
    two = ProjectContract.load(_contract_at(tmp_path / "two"))
    assert one.repository() != two.repository(), (
        f"two projects both declaring `repo_path: \".\"` resolved to one repository "
        f"({one.repository()})"
    )


def test_an_absolute_declared_repository_is_left_exactly_as_declared(tmp_path):
    """The repair must not rewrite a declaration that already names a place.

    THROUGH A SYMLINK, deliberately. `parent / absolute` already yields the
    absolute path, so a first version of this oracle passed against a repair
    that dropped the short-circuit and called `.resolve()` on everything — and
    `.resolve()` follows symlinks, which silently rewrites a declaration the
    project made on purpose. On this platform `/tmp` is itself such a link, so
    the difference is not exotic.
    """
    real = tmp_path / "real-place"
    real.mkdir()
    linked = tmp_path / "declared-through-a-link"
    linked.symlink_to(real, target_is_directory=True)

    contract = ProjectContract.load(_contract_at(tmp_path / "proj", repo_path=f'"{linked}"'))
    assert contract.repository() == str(linked), (
        f"an absolute declaration came back as {contract.repository()!r} rather than as "
        f"{str(linked)!r}; the project named a path and the pack rewrote it"
    )


def test_an_explicit_override_still_wins_over_the_declaration(tmp_path):
    """The override is how a caller says *this repository, not the declared one*."""
    contract = ProjectContract.load(_contract_at(tmp_path / "proj"))
    assert contract.repository("/somewhere/given/explicitly") == "/somewhere/given/explicitly"


def test_a_contract_loaded_by_a_relative_path_answers_the_same_from_anywhere(tmp_path, monkeypatch):
    """The defect in the FIRST repair of this class, found by an independent reader.

    `repository()` resolves against `self.path.parent`, and a contract loaded by
    a relative path — which is exactly how a CLI invoked from the project loads
    one — kept that parent relative. The same object then answered differently
    from two working directories, so the repair moved the dependency rather than
    removing it.
    """
    project = tmp_path / "A"
    elsewhere = tmp_path / "B"
    project.mkdir()
    elsewhere.mkdir()
    _contract_at(project)

    monkeypatch.chdir(project)
    contract = ProjectContract.load("PROJECT.yaml")
    assert Path(contract.path).is_absolute(), (
        f"the contract kept a relative path ({contract.path}); everything resolved against "
        f"its parent is then relative to the process")
    from_project = contract.repository()
    monkeypatch.chdir(elsewhere)
    assert contract.repository() == from_project, (
        f"one contract object answered {from_project} from its own directory and "
        f"{contract.repository()} from another")


@pytest.mark.parametrize("declared,names", [
    ("link/..", "external"),
    ("link", "child"),
    (".", "proj"),
    ("../external", "external"),
])
def test_a_relative_declaration_names_what_the_filesystem_says_it_names(
        tmp_path, declared, names):
    """TWO WRONG ANSWERS PRECEDED THE RIGHT ONE, and both are parametrised here.

    `.resolve()` follows symlinks, so it rewrote a declaration the project made
    through a link while the absolute branch preserved it. `os.path.normpath`
    then collapsed `..` LEXICALLY, before the filesystem interpreted the link —
    so `link/..`, where `link` points into another tree, named the contract's own
    directory instead of the link's parent, and a caller would have scanned the
    wrong repository again. Found by a bounded reading of that repair.

    The property is not about the SPELLING of the answer: it is that the answer
    names what the project named. So each case is compared by what the
    filesystem resolves it to.
    """
    (tmp_path / "external" / "child").mkdir(parents=True)
    project = tmp_path / "proj"
    project.mkdir()
    (project / "link").symlink_to(tmp_path / "external" / "child", target_is_directory=True)
    expected = {"external": tmp_path / "external",
                "child": tmp_path / "external" / "child",
                "proj": project}[names]

    (project / "PROJECT.yaml").write_text(
        f'project:\n  name: p\n  repo_path: "{declared}"\n'
        'pack:\n  root_path: "/nowhere"\n'
        "capabilities:\n  - id: C1\n", encoding="utf-8")

    resolved = ProjectContract.load(project / "PROJECT.yaml").repository()
    assert Path(resolved).is_absolute(), f"{resolved} is not absolute"
    assert Path(resolved).resolve() == expected.resolve(), (
        f"`repo_path: {declared!r}` names {expected}, and the contract returned {resolved}, "
        f"which the filesystem reads as {Path(resolved).resolve()}")

    # AND THE SPELLING, because the absolute branch returns a declaration
    # verbatim and the two branches must not disagree about whether the pack
    # rewrites what a project wrote. `.resolve()` reaches the same destination
    # for every case above and still rewrites the path, which is why the
    # destination assertion alone let a mutant restoring it survive.
    assert resolved == str(project / declared), (
        f"the contract rewrote `{declared}` to {resolved!r}. An absolute declaration is "
        f"returned as declared; a relative one is rooted and otherwise left alone")
