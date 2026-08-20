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
