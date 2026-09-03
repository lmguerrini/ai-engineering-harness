"""D4: the commit contract accepts two to four bullets, not exactly three."""

import subprocess
import sys
from pathlib import Path

import pytest

import commit_gate

TOOLS_DIR = Path(__file__).resolve().parent.parent


def _message(*bullets: str, title: str = "Fix the widget") -> str:
    body = "\n".join(f"- {bullet}" for bullet in bullets)
    return f"{title}\n\n{body}\n"


def test_two_bullets_accepted():
    violations = commit_gate.validate_message(_message("first outcome", "second outcome"), commit_gate.NO_PRIVATE_TERMS)
    assert violations == []


def test_three_bullets_accepted():
    violations = commit_gate.validate_message(
        _message("first outcome", "second outcome", "third outcome"), commit_gate.NO_PRIVATE_TERMS
    )
    assert violations == []


def test_four_bullets_accepted():
    violations = commit_gate.validate_message(
        _message("one", "two", "three", "four"), commit_gate.NO_PRIVATE_TERMS
    )
    assert violations == []


def test_one_bullet_rejected():
    violations = commit_gate.validate_message(_message("only outcome"), commit_gate.NO_PRIVATE_TERMS)
    rules = {v.rule for v in violations}
    assert "BULLET_COUNT" in rules


def test_five_bullets_rejected():
    violations = commit_gate.validate_message(
        _message("one", "two", "three", "four", "five"), commit_gate.NO_PRIVATE_TERMS
    )
    rules = {v.rule for v in violations}
    assert "BULLET_COUNT" in rules


def test_credential_pattern_caught():
    message = _message("added a client using sk-ant-abcdefghijklmnopqrstuvwx0123456789", "cleaned up tests")
    violations = commit_gate.validate_message(message, commit_gate.NO_PRIVATE_TERMS)
    rules = {v.rule for v in violations}
    assert "CREDENTIAL" in rules


def test_local_path_caught():
    message = _message("fixed a bug in /Users/alice/project/loader.py", "added a test")
    violations = commit_gate.validate_message(message, commit_gate.NO_PRIVATE_TERMS)
    rules = {v.rule for v in violations}
    assert "ABSOLUTE_PATH" in rules


def test_repository_relative_path_is_not_a_violation():
    message = _message("fixed a bug in src/loader.py", "added a test")
    violations = commit_gate.validate_message(message, commit_gate.NO_PRIVATE_TERMS)
    rules = {v.rule for v in violations}
    assert "ABSOLUTE_PATH" not in rules


def test_private_term_caught_and_redacted_without_reproducing_the_secret():
    term_set = commit_gate.TermSet.of(terms=["projectcodename"])
    message = _message("shipped the projectcodename integration", "added a test")
    violations = commit_gate.validate_message(message, term_set)
    rendered = "; ".join(str(v) for v in violations)
    assert any(v.rule == "PRIVATE_TERM" for v in violations)
    # The redaction must not reproduce the full term verbatim in the report.
    assert "projectcodename" not in rendered


def test_missing_term_set_is_a_type_error():
    with pytest.raises(TypeError):
        commit_gate.validate_message(_message("a", "b"), None)


def test_bullet_shape_regex_matches_two_through_four():
    assert commit_gate.SHAPE.fullmatch(_message("a", "b"))
    assert commit_gate.SHAPE.fullmatch(_message("a", "b", "c"))
    assert commit_gate.SHAPE.fullmatch(_message("a", "b", "c", "d"))
    assert not commit_gate.SHAPE.fullmatch(_message("a"))
    assert not commit_gate.SHAPE.fullmatch(_message("a", "b", "c", "d", "e"))


def _run_cli(stdin: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / "commit_gate.py"), *args],
        input=stdin, capture_output=True, text=True, cwd=str(TOOLS_DIR),
    )


def test_cli_accepts_valid_message_from_stdin():
    result = _run_cli(_message("a", "b"))
    assert result.returncode == 0
    assert "VALID" in result.stdout


def test_cli_rejects_and_prints_each_violation():
    result = _run_cli(_message("only one"))
    assert result.returncode != 0
    assert "VIOLATION" in result.stdout


# --- F5: the read-back side must accept git's own output -------------------
# `git log -1 --format=%B` terminates the message with TWO newlines. Stripping
# only one leaves a blank line that reads as EXTRA_CONTENT, so the read-back
# half of the double-sided contract failed on every well-formed commit.

GOOD = (
    "Summarize a numeric column from a CSV file\n"
    "\n"
    "- Report count, minimum, maximum and mean for a named column\n"
    "- Refuse a missing column, naming what was wrong\n"
)


def test_git_format_B_readback_is_accepted():
    assert commit_gate.validate_message(GOOD + "\n", commit_gate.NO_PRIVATE_TERMS) == []


def test_many_trailing_newlines_are_still_accepted():
    assert commit_gate.validate_message(GOOD + "\n\n\n", commit_gate.NO_PRIVATE_TERMS) == []


def test_real_prose_after_bullets_is_still_refused():
    bad = GOOD + "\nThis trailing paragraph is real content.\n"
    codes = [v.rule for v in commit_gate.validate_message(bad, commit_gate.NO_PRIVATE_TERMS)]
    assert "EXTRA_CONTENT" in codes


# --- the range gate: drift across a branch ----------------------------------
#
# `validate_range` shipped in 2.1.0 with **no test at all**,
# although the drift it detects — a convention that breaks once and never
# recovers — is easy to construct. A permanent regression test is cheap here
# because the property is deterministic: build a branch whose drift point is
# known, and assert the gate names exactly that point.


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


@pytest.fixture
def drifting_history(tmp_path):
    """Five conforming commits, then three that drift, in that order."""
    repo = tmp_path / "history"
    repo.mkdir()
    _git(repo, "init", "--quiet", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Ordinary Human")
    _git(repo, "config", "user.email", "human@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")

    conforming, drifting = [], []
    for index in range(8):
        (repo / f"f{index}.txt").write_text(f"{index}\n")
        _git(repo, "add", f"f{index}.txt")
        if index < 5:
            message = _message("first outcome", "second outcome", title=f"Add file number {index}")
        else:
            message = f"wip {index}\n"
        _git(repo, "commit", "--quiet", "-m", message)
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
        ).stdout.strip()
        (conforming if index < 5 else drifting).append(sha)
    return repo, conforming, drifting


def test_a_range_reports_exactly_the_commits_that_drifted(drifting_history):
    repo, conforming, drifting = drifting_history
    failures = commit_gate.validate_range(str(repo), "refs/heads/main", None, commit_gate.NO_PRIVATE_TERMS)

    reported = {sha for sha, _ in failures}
    assert reported == set(drifting)
    assert reported.isdisjoint(conforming)
    assert all(violations for _, violations in failures)


def test_a_range_of_conforming_commits_is_clean(drifting_history):
    """The drift point is a boundary, so the clean side is asserted too."""
    repo, conforming, _ = drifting_history
    failures = commit_gate.validate_range(
        str(repo), conforming[-1], None, commit_gate.NO_PRIVATE_TERMS
    )
    assert failures == []


def test_a_baseline_excludes_history_before_it(drifting_history):
    """Range drift is asked about an unpublished segment, not all of history."""
    repo, conforming, drifting = drifting_history
    failures = commit_gate.validate_range(
        str(repo), "refs/heads/main", conforming[-1], commit_gate.NO_PRIVATE_TERMS
    )
    assert {sha for sha, _ in failures} == set(drifting)


def test_the_single_message_gate_cannot_see_range_drift(drifting_history):
    """Why the range surface exists, stated as a test rather than as a comment.

    Every one of those commits passed a gate at the moment it was made — the
    check runs before staging and on read-back, and then nothing ever re-reads
    the message again.
    """
    repo, _, drifting = drifting_history
    import gitread

    drifted = gitread.commit_message(str(repo), drifting[0])
    assert commit_gate.validate_message(drifted, commit_gate.NO_PRIVATE_TERMS)
    failures = commit_gate.validate_range(str(repo), drifting[0], None, commit_gate.NO_PRIVATE_TERMS)
    assert failures, "the range surface is the only one that re-reads a committed message"


# --- EC-B: a Conventional Commit subject is not a trailer --------------------
#
# Reproduced against the frozen 2.1.1 baseline before repair: `fix: correct the
# parser` was refused `TRAILER` while `feat: …` passed, because `fix` is in the
# trailer token set and the detector never asked *where* on the message the
# match occurred. The commit contract asks for a Conventional Commit subject, so
# the gate was refusing the form it requires.


def _codes(message):
    return [str(violation).split(":")[0] for violation in
            commit_gate.validate_message(message, commit_gate.NO_PRIVATE_TERMS)]


BODY = "\n\n- one bullet here\n- two bullet here\n"


@pytest.mark.parametrize(
    "subject",
    [
        "fix: correct the parser",        # the reproduced defect
        "feat: add the thing",
        "fix(pathmatch): correct it",
        "fix!: breaking change",
        "refactor(a/b): move it",
        "revert: undo it",
        "docs: update the readme",
        "perf: speed it up",
        "test: add the missing cases",
        "build: bump the toolchain",
        "ci: run the suite on push",
        "chore: tidy up",
        "style: reflow the prose",
    ],
)
def test_a_conventional_commit_subject_is_accepted(subject):
    assert _codes(subject + BODY) == []


@pytest.mark.parametrize(
    "subject",
    [
        "Signed-off-by: A Person",
        "Reviewed-by: A Person",
        "Change-Id: I0123456789",
        "Closes: #3",
    ],
)
def test_a_real_trailer_as_the_subject_is_still_refused(subject):
    """The exemption is for the Conventional type set, not for line 1."""
    assert "TRAILER" in _codes(subject + BODY)


@pytest.mark.parametrize(
    "body",
    [
        "\n\n- one bullet here\n- Fixes: #12\n",
        "\n\n- one bullet here\n- Signed-off-by: A Person\n",
        "\n\n- one bullet here\n- Change-Id: I0123456789\n",
    ],
)
def test_a_trailer_in_the_body_is_refused_under_a_conventional_subject(body):
    """A trailer does not become legal by sitting under an exempted subject."""
    assert "TRAILER" in _codes("fix: correct the parser" + body)


def test_a_subject_that_merely_starts_with_a_type_word_is_not_exempted():
    """`fixing:` and `features:` are not Conventional Commit types, and the
    exemption must not widen to anything that begins with one."""
    assert "TRAILER" in _codes("fix-it-later: something" + BODY)


def test_co_authored_by_is_still_refused_as_a_subject():
    assert "COAUTHOR" in _codes("Co-authored-by: An Assistant" + BODY)


@pytest.mark.parametrize(
    "subject",
    [
        "fix: Signed-off-by: A Person",
        "feat: Change-Id: I0123456789",
        "test: Fixes: #12",
        "chore: Reviewed-by: A Person",
        "refactor(core): Closes: #3",
    ],
)
def test_a_trailer_behind_a_conventional_prefix_is_still_refused(subject):
    """The first repair blanked the whole subject line, so `fix: Signed-off-by:
    A Person` passed clean — the docstring claimed otherwise and an independent
    audit caught it. Only the matched prefix is removed now."""
    assert "TRAILER" in _codes(subject + BODY)


def test_co_authored_by_behind_a_conventional_prefix_is_still_refused():
    assert "COAUTHOR" in _codes("fix: Co-authored-by: An Assistant" + BODY)


@pytest.mark.parametrize(
    "subject",
    [
        # Extra whitespace after the prefix. 2.1.1 REFUSED these; the first
        # repair accepted them, which made it a regression rather than a gap.
        "fix:  Signed-off-by: A Person",
        "fix:   Signed-off-by: A Person",
        "fix:\tSigned-off-by: A Person",
        "feat!:  Reviewed-by: X",
        "fix(parser):  Change-Id: I0123456789",
        # A second prefix in front of the trailer.
        "fix: docs: Signed-off-by: A Person",
        "feat: chore: Reviewed-by: Someone",
        "fix(a)!: test: Change-Id: Iabc123",
        # Not a regression — 2.1.1 let this through too — but the same hole.
        "docs:  Reviewed-by: Someone Else",
    ],
)
def test_no_amount_of_prefix_or_whitespace_hides_a_trailer(subject):
    """Two independent audits reproduced this. The trailer patterns anchor with
    `^`, so anything left in front of the token hides it — which is what the
    first repair's own docstring said it had avoided."""
    assert "TRAILER" in _codes(subject + BODY)


@pytest.mark.parametrize(
    "subject",
    [
        "fix:  extra spaces before an ordinary subject",
        "fix: docs: an odd but legitimate subject",
        "refactor(core):   spaced out",
    ],
)
def test_extra_whitespace_and_repeated_prefixes_are_still_accepted_when_clean(subject):
    """The strengthening must not start refusing ordinary messages."""
    assert _codes(subject + BODY) == []


# --- the whole surface, against the qualified baseline -------------------------


def _baseline_commit_gate():
    """The frozen 2.1.1 module, loaded from git rather than from disk."""
    import importlib.util
    import subprocess
    import tempfile
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    source = subprocess.run(
        ["git", "show", "4495e61850c08027e47eac6d0db84b4b3380e300:tools/commit_gate.py"],
        cwd=str(root), capture_output=True, check=True,
    ).stdout.decode("utf-8")
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "baseline_commit_gate.py"
        path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("baseline_commit_gate", path)
        module = importlib.util.module_from_spec(spec)
        # Registered before execution: `dataclasses` resolves a string
        # annotation through `sys.modules[cls.__module__]`, which does not
        # exist yet while the class body is running.
        import sys

        sys.modules["baseline_commit_gate"] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop("baseline_commit_gate", None)
        return module


#: The one thing this release deliberately stopped refusing is EC-B: `fix` is in
#: the trailer token set, so a Conventional `fix:` subject was refused for being
#: a trailer when nothing about it was one.
#:
#: Deciding whether a given loss *is* that is not "does the subject start with
#: `fix:`" — that exemption was written first and excused every `fix:` subject,
#: including `fix: docs: Signed-off-by:`, which is precisely the regression this
#: test exists to catch. A falsification run proved the exemption swallowed it.
#:
#: Substituting a neutral type word and re-asking the *baseline* was the second
#: attempt, and it was also wrong: the baseline never detected a trailer sitting
#: after a prefix — it is `^`-anchored, so `feat: Signed-off-by:` was clean there
#: — which made it excuse the very losses it was meant to catch. The baseline is
#: the wrong oracle for a hole the baseline could not see.
#:
#: So the question is answered independently of both modules: **does the tail
#: bear a trailer at all?** Strip any leading `word:` groups from it and look. A
#: subject that loses `TRAILER` while its tail bears one is a regression whatever
#: the reason the baseline had for refusing it — the observable guarantee was
#: "this message is refused", and it stopped holding.


def _tail_bears_a_trailer(tail: str) -> bool:
    """Whether this subject tail carries a trailer, judged without either module.

    Deliberately a small reimplementation. Asking the module under test whether
    its own input is trailer-shaped is not an oracle.
    """
    import re

    remainder = tail
    while True:
        stripped = re.sub(r"^[A-Za-z][A-Za-z0-9]*(?:\([^()]*\))?!?:\s+", "", remainder)
        if stripped == remainder:
            break
        remainder = stripped
        if _looks_like_a_trailer(remainder):
            return True
    return _looks_like_a_trailer(tail)


def _looks_like_a_trailer(text: str) -> bool:
    """One line, judged for trailer shape. **Unicode-aware on purpose.**

    An ASCII-only version of this was written first and quietly excused a
    regression: `Ünicode-Trailer:` is trailer-*shaped*, so a lost refusal on it
    is a lost refusal, and an oracle that cannot see the shape cannot judge the
    loss. The implementation had the same ASCII assumption, which is exactly why
    an oracle that shares it is no oracle.
    """
    import re

    return bool(
        re.match(r"^[^\W\d_][^\W_]*(?:-[^\W_]+)+\s*:", text)
        or re.match(r"^(?:signed|reviewed|acked|tested|reported|suggested|helped|cc|refs?"
                    r"|closes?|fixe?s?|resolves?|change-id|bug|ticket|issue|see-also|link)\s*:",
                    text, re.IGNORECASE)
    )


def test_nothing_the_qualified_baseline_refused_is_accepted_except_the_one_intended_change():
    """A differential over the whole subject surface, against 2.1.1.

    Written because a repair to this module *did* regress it — `fix:` followed
    by two spaces, and `fix: docs:`, let a trailer through that the baseline
    refused, and two independent audits had to find it. A parametrised list of
    literal cases could not have: it would have contained the forms somebody
    thought of, which is the same failure the module's own history is about.
    """
    import itertools

    baseline = _baseline_commit_gate()
    old_terms = baseline.TermSet(declared_empty=True)
    new_terms = commit_gate.TermSet(declared_empty=True)

    types = ["fix", "feat", "docs", "chore", "refactor", "test", "perf", "build",
             "ci", "style", "revert", "fixup", "wip"]
    scopes = ["", "(core)", "(a/b)", "!"]
    spacing = ["", " ", "  ", "   ", "\t", " \t "]
    tails = ["Signed-off-by: A Person", "Reviewed-by: X", "Change-Id: I0123",
             "Closes: #3", "Fixes: #12", "Co-authored-by: X", "Link: http://x",
             "ordinary subject text", "Relates-to: Y",
             # A second Conventional prefix in front of the trailer. Without
             # these the grid cannot see a single-pass prefix strip, and a
             # falsification run proved it could not — the same shape of gap as
             # the pathmatch grid that could not see a trailing `**`.
             "docs: Signed-off-by: A Person", "chore: Reviewed-by: X",
             "test: Change-Id: I0123", "feat: ordinary subject text",
             # Non-ASCII trailer tokens. `[A-Za-z]` let `Ünicode-Trailer:`
             # through once the prefix in front of it was removed — the same
             # lost-refusal class, found by probing rather than by review.
             "Ünicode-Trailer: value", "Ärger-Bericht: x", "Ünicode subject text",
             # Casing and spacing variants of a real token.
             "signed-off-by: a person", "SIGNED-OFF-BY: A Person",
             "Signed-off-by:no space", "- Signed-off-by: A Person"]

    def codes(module, terms, message):
        return {str(violation).split(":")[0]
                for violation in module.validate_message(message, terms)}

    regressions = []
    strengthened = 0
    intended = 0
    for kind, scope, gap, tail in itertools.product(types, scopes, spacing, tails):
        subject = f"{kind}{scope}:{gap}{tail}"
        message = subject + BODY
        was = codes(baseline, old_terms, message)
        now = codes(commit_gate, new_terms, message)
        lost = was - now
        if not lost:
            strengthened += bool(now - was)
            continue
        if lost == {"TRAILER"} and not _tail_bears_a_trailer(tail):
            intended += 1
        else:
            regressions.append((subject, sorted(lost)))
        strengthened += bool(now - was)

    assert not regressions, (
        "the candidate accepts what the qualified baseline refused: "
        + "; ".join(f"{subject!r} lost {lost}" for subject, lost in regressions[:10])
    )
    assert strengthened > 100, (
        f"only {strengthened} subjects got stricter; the differential is not exercising the surface"
    )
    assert intended > 0, "the differential no longer covers the one intended weakening"


# --- an absolute property, not a differential ---------------------------------
#
# Four round-3 repairs — the leading-whitespace class, an empty scope `()`, a
# doubled `!!`, and two scope groups `(a)(b)` — could each be reverted with the
# whole suite still green. An audit found it by mutation rather than by reading,
# and the reason none of the existing tests could see it is instructive:
#
#   * the parametrised list contained the decorations somebody had thought of;
#   * the differential against 2.1.1 is structurally blind to anything 2.1.1 also
#     let through, which the leading-whitespace class is.
#
# So this asserts the property **absolutely**, over generated decorations, with
# no reference to the previous release. If a subject's tail bears a trailer, the
# gate refuses the message. Nothing about how the subject is decorated changes
# that.

_TRAILER_TAILS = [
    "Signed-off-by: A Person",
    "Reviewed-by: X",
    "Change-Id: I0123456789",
    "Acked-by : Some Body",          # git parses a space before the colon
    "Relates-to:no-space",
    "X-Custom-Header: value",
]

#: Every way a subject can be decorated in front of the trailer. Generated as a
#: product rather than listed, so a decoration nobody thought of is still
#: covered by construction.
_TYPES = ["fix", "feat", "docs", "chore", "refactor", "revert"]
_SCOPES = ["", "()", "(core)", "(a/b)", "(a)(b)", "(a(b))"]
_BANGS = ["", "!", "!!"]
_GAPS = [" ", "  ", "\t", " \t ", " ", " ", "​", ""]
_LEADS = ["", " ", "  ", "\t", " "]


@pytest.mark.parametrize("tail", _TRAILER_TAILS)
def test_a_subject_whose_tail_bears_a_trailer_is_always_refused(tail):
    """The absolute property. Every decoration, every gap, every lead."""
    import itertools

    escaped = []
    for lead, kind, scope, bang, gap in itertools.product(
        _LEADS, _TYPES, _SCOPES, _BANGS, _GAPS
    ):
        subject = f"{lead}{kind}{scope}{bang}:{gap}{tail}"
        if not _codes(subject + BODY):
            escaped.append(subject)
    assert not escaped, (
        f"{len(escaped)} decorated subjects carrying {tail!r} passed clean, e.g. "
        + "; ".join(repr(subject) for subject in escaped[:5])
    )


def test_a_bare_trailer_is_refused_however_the_line_begins():
    """No prefix at all — only leading whitespace and bullet markers."""
    escaped = []
    for lead in _LEADS + ["- ", " - ", "- ", "-\t"]:
        for tail in _TRAILER_TAILS:
            if not _codes(lead + tail + BODY):
                escaped.append(lead + tail)
    assert not escaped, f"these passed clean: {escaped[:5]}"


#: Tails that only ONE of the two trailer patterns can catch. Using a tail both
#: match — `Signed-off-by` is a token *and* hyphenated — lets a mutation of
#: either pattern survive, because the other still fires. That is how two
#: mutations survived the first version of these tests.
_TOKEN_ONLY_TAIL = "Closes: #3"                     # in the token set, not hyphenated
_HYPHENATED_ONLY_TAIL = "X-Custom-Header: value"    # hyphenated, not a token


@pytest.mark.parametrize("tail", [_TOKEN_ONLY_TAIL, _HYPHENATED_ONLY_TAIL])
def test_a_trailer_on_a_body_bullet_is_refused_however_the_bullet_is_spaced(tail):
    """Where round 4's first blocker lived: the bullet-marker group had been
    narrowed from ``\\s`` to ``[ \\t]``, so a Unicode space after the dash hid the
    token. The differential never looked at the body at all."""
    escaped = []
    for gap in [" ", "  ", "\t", "\u00a0", "\u2003", "\u202f", "\u3000", "\u2009"]:
        message = f"A title line\n\n- a real outcome\n-{gap}{tail}\n"
        if "TRAILER" not in _codes(message):
            escaped.append(repr(gap))
    assert not escaped, f"a trailer hid behind these bullet gaps: {escaped}"


@pytest.mark.parametrize("tail", [_TOKEN_ONLY_TAIL, _HYPHENATED_ONLY_TAIL])
def test_each_trailer_pattern_is_exercised_on_its_own(tail):
    """One tail each pattern alone must catch, so a mutation of either fails."""
    assert "TRAILER" in _codes(f"fix: {tail}" + BODY)
    assert "TRAILER" in _codes(f"  {tail}" + BODY)


@pytest.mark.parametrize("tail", [_TOKEN_ONLY_TAIL, _HYPHENATED_ONLY_TAIL])
def test_an_invisible_character_does_not_hide_the_trailer_behind_it(tail):
    """The refusal rule and the surface normalisation are two separate repairs,
    and only the rule was pinned. Removing the normalisation still refuses the
    message — but as ``INVISIBLE_CHARACTER`` alone, so the reader is told the
    wrong thing about what is in their commit."""
    for character in ["\u200b", "\ufeff", "\u00ad", "\u061c"]:
        codes = _codes(f"fix: {character}{tail}" + BODY)
        assert "TRAILER" in codes, f"U+{ord(character):04X} hid the trailer: {codes}"


def test_an_invisible_character_is_refused_in_its_own_right():
    """The `INVISIBLE_CHARACTER` rule had no behavioural test at all — disabling
    it left the whole suite green, and it is the guard added to close an
    audit-found regression."""
    for character in ["​", "⁠", "﻿", "­", "‮", "؜"]:
        codes = _codes(f"fix: an ordinary{character} subject" + BODY)
        assert "INVISIBLE_CHARACTER" in codes, (
            f"U+{ord(character):04X} was not refused: {codes}"
        )


def test_ordinary_text_is_not_refused_as_invisible():
    """The rule must not fire on accented, non-Latin or punctuated prose."""
    for subject in ["fix: café menu update", "docs: 日本語のタイトル",
                    "feat: naïve — em dash and “curly quotes”", "chore: ∑ and ≤"]:
        assert "INVISIBLE_CHARACTER" not in _codes(subject + BODY), subject


# --- the pack's own vocabulary, for a repository with no contract ---------------
#
# Found by a coordinator error rather than by design: a hand-written substring
# check reported a private term in a commit message, and the shipped scanner —
# which word-bounds a bare term — reported the same message clean. The message
# was fine; the instrument was not the one that ships. The reason the ad-hoc
# check existed at all is that this repository has no project contract, so its
# own commits could be checked structurally or not at all.

import json as _json

import pytest as _pytest

import commit_gate as _commit_gate
from errors import GateRefusal as _GateRefusal


class _Args:
    def __init__(self, **fields):
        self.project = None
        self.term = []
        self.pattern = []
        self.default_terms = None
        self.__dict__.update(fields)


def _pack(tmp_path, **overrides):
    root = tmp_path / "pack"
    (root / "policy").mkdir(parents=True)
    payload = {"policy_schema": 2, "terms": ["engineering harness"], "identity_terms": ["sol"],
               "patterns": [], "identity_patterns": [], "optional_patterns": {}}
    payload.update(overrides)
    (root / "policy" / "private-terms.default.json").write_text(_json.dumps(payload))
    return root


def test_the_pack_default_vocabulary_can_be_applied_without_a_contract(tmp_path):
    term_set = _commit_gate._term_set_from_args(_Args(default_terms=str(_pack(tmp_path))))
    assert "engineering harness" in term_set.terms
    assert "sol" in term_set.identity_terms


def test_a_bare_term_is_word_bounded_and_does_not_match_inside_a_word(tmp_path):
    """The exact false positive: a naive substring check found `sol` in
    `resolves`. The shipped scanner does not, and the difference between the
    two instruments is the whole finding."""
    term_set = _commit_gate._term_set_from_args(_Args(default_terms=str(_pack(tmp_path))))
    assert term_set.offenders("resolves") == []
    assert term_set.offenders("console") == []
    assert term_set.offenders("sol") == ["sol"]


def test_a_multi_word_term_still_matches_where_it_appears(tmp_path):
    term_set = _commit_gate._term_set_from_args(_Args(default_terms=str(_pack(tmp_path))))
    assert term_set.offenders("the engineering harness ran") == ["engineering harness"]


def test_the_default_vocabulary_is_read_from_the_declared_root_and_reports_its_source(tmp_path):
    """Through the same resolution every other rule goes through, so a copy in
    a working directory cannot stand in for the one the release ships."""
    args = _Args(default_terms=str(_pack(tmp_path)))
    _commit_gate._term_set_from_args(args)
    source = getattr(args, "_rule_source")
    assert source.canonical and len(source.digest) == 64


def test_a_pack_root_with_no_default_vocabulary_is_refused_rather_than_emptied(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with _pytest.raises(_GateRefusal):
        _commit_gate._term_set_from_args(_Args(default_terms=str(empty)))


def test_the_pack_defaults_are_additive_to_the_flags_like_everything_else(tmp_path):
    term_set = _commit_gate._term_set_from_args(
        _Args(default_terms=str(_pack(tmp_path)), term=["a project term"]))
    assert "a project term" in term_set.terms and "engineering harness" in term_set.terms
