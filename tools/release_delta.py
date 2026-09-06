"""What a release's CHANGELOG entry must cover, computed from the release itself.

`CHANGELOG.md` is this pack's canonical per-release delta and has been since
2.0.0: one section per version, describing that version **against the one before
it** rather than restating the whole pack. This module does not replace it and
does not add a second release-history system. It answers one question about it:

    does this version's entry account for what this version actually changed?

**Why it exists.** The 2.4.0 entry was written partway through the release and
then stopped being updated. By the end it named one of four new tools, none of
eight new test modules, two of fourteen new tracked files and one of two new
decisions — so a reader asking *what changed from 2.3.0 to 2.4.0* would have had
to reconstruct it from the commit range, which is the thing a changelog exists to
make unnecessary.

**What is authoritative here is the repository, not this file.** The categories
below are derived by diffing the release range: a file the release added is a
change the release made, and a decision it recorded is a change to how the pack
is governed. Nothing is transcribed and no count is stored.

**What this cannot do.** It cannot judge whether the entry describes a change
*well*, or whether a change that added no file is described at all — a repair
inside an existing module is invisible to it. It establishes coverage of the
things a diff can name, which is the half that was silently missing, and it is
not a substitute for writing the entry.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Delta", "additions", "entry_for", "coverage", "CATEGORY"]


#: How a path is described to a reader who is deciding whether the entry should
#: name it. Ordered: the first pattern that matches wins.
CATEGORY = (
    ("tools/tests/", "a test module"),
    ("tools/", "a tool a consuming project runs"),
    ("policy/", "a governed policy surface"),
    ("templates/", "a template a project installs or copies"),
    ("skills/", "a skill loaded every session"),
    ("docs/", "a release record or design record"),
    ("", "a tracked file"),
)


def _category(path: str) -> str:
    for prefix, description in CATEGORY:
        if path.startswith(prefix):
            return description
    return "a tracked file"  # pragma: no cover - the empty prefix always matches


@dataclass(frozen=True)
class Delta:
    """One thing the release added, and how a reader would recognise it."""

    path: str
    category: str
    #: The token an entry is expected to contain. A file is named by its path or
    #: by its basename; a decision by its identifier.
    token: str


def _tree(repository: str | Path, revision: str) -> set:
    """Through the one boundary, like every other read in this toolbelt.

    This module ran Git directly, with the caller's whole environment inherited
    and no construction around it. No execution was ever reproduced from it — an
    independent certification rated it a documentation-accuracy point — but it was
    a second path to the same question that could answer differently from the
    first, which is the thing `docs/RP2.5.0-DESIGN-A1-sterile-execution.md` exists
    to remove. One boundary, one answer.
    """
    import gitread

    try:
        # `-z`, like every other path enumeration in this toolbelt. Without it Git
        # C-quotes any path it cannot print literally, so a file with a space or a
        # non-ASCII name reaches the delta as an escaped literal and is compared
        # against a name nothing has. This module was routed through the boundary
        # and kept its old argument list; the pack's own rule caught it.
        return set(gitread.nul_paths(
            gitread._run(repository, "ls-tree", "-r", "-z", "--name-only", revision,
                         timeout=120, text=False)))
    except Exception as exc:
        raise RuntimeError(f"cannot read the tree at {revision}: {exc}") from exc


def _decisions(repository: str | Path, revision: str) -> set:
    """Through the one boundary. A release with no `DECISIONS.md` is an answer."""
    import gitread

    try:
        shown = gitread._run(repository, "show", f"{revision}:DECISIONS.md", timeout=120)
    except Exception:
        return set()
    return set(re.findall(r"^## (D\d+)", shown, re.M))


def additions(repository: str | Path, *, baseline: str, revision: str = "HEAD") -> tuple:
    """Everything this release added that a diff can name.

    Additions only, deliberately. A file the release DELETED is a change too, and
    naming it is good practice — but a deletion is not something a reader can
    look up afterwards, and requiring an entry to name every removed file would
    make the check fire on tidying. What it must not do is add something and say
    nothing.
    """
    added = sorted(_tree(repository, revision) - _tree(repository, baseline))
    found = [Delta(path, _category(path), Path(path).name) for path in added]
    for decision in sorted(_decisions(repository, revision)
                           - _decisions(repository, baseline)):
        found.append(Delta(f"DECISIONS.md::{decision}", "a pack-level decision", decision))
    return tuple(found)


def entry_for(changelog: str, version: str) -> str:
    """The one section of the changelog that describes this version.

    Raises rather than returning an empty string: a version with no entry and a
    version with an empty one are different failures, and the second is the one
    somebody would try to satisfy by adding a heading.
    """
    # THE WHOLE HEADING LINE, not just the version. Matching only the version
    # left the heading's own title inside the body, so an entry that was a
    # heading and nothing else read as non-empty — which is the obvious way to
    # satisfy a check that looks for a heading. Its own test found that.
    # `\b` ACCEPTS A HYPHEN, so `## 9.9.9-rc.1` satisfied a request for `9.9.9`
    # and one version's entry stood in for another's. The version must be
    # followed by the end of the token, which in these headings is a space, an
    # em dash or the end of the line — never another version character. Found by
    # an independent reading.
    match = re.search(rf"^## {re.escape(version)}(?![0-9A-Za-z.\-_+])[^\n]*$", changelog, re.M)
    if not match:
        raise ValueError(f"the changelog has no `## {version}` entry")
    rest = changelog[match.end():]
    following = re.search(r"^## ", rest, re.M)
    body = rest[:following.start()] if following else rest
    if not body.strip():
        raise ValueError(f"the `## {version}` entry is empty")
    return body


def _names(entry: str, token: str) -> bool:
    """Whether the entry names this token, as a token rather than as a substring.

    **SUBSTRING MEMBERSHIP IS NOT NAMING**, and this pack has the failure in its
    own recurrence classes as *substring-based semantic comparison*. Written that
    way, `tools/evolution_evidence.py` counted as named because
    `evolution_evidence.py` occurs inside `test_evolution_evidence.py`, and an
    omitted decision `D9` counted as named because `D90` was there. Both found by
    an independent reading of the check's first version.

    The boundary is the set of characters that can appear in a filename or a
    decision identifier, so `evolution_evidence.py` does not match inside
    `test_evolution_evidence.py` and `D9` does not match inside `D90`.
    """
    # THE BOUNDARY DEPENDS ON THE TOKEN, because a period continues a filename
    # and ends a sentence. With one boundary set for both, `recorded D9.` did
    # not name `D9` — the trailing full stop read as part of the identifier —
    # and the check reported an omission nobody had made.
    continues = r"0-9A-Za-z._-" if "." in token else r"0-9A-Za-z_-"
    boundary = rf"[^{continues}]"
    pattern = rf"(?:^|{boundary})" + re.escape(token) + rf"(?:$|{boundary})"
    return re.search(pattern, entry) is not None


@dataclass(frozen=True)
class Coverage:
    version: str
    baseline: str
    named: tuple = field(default_factory=tuple)
    omitted: tuple = field(default_factory=tuple)

    @property
    def complete(self) -> bool:
        return not self.omitted

    def render(self) -> str:
        lines = [f"release delta {self.baseline[:12]} -> {self.version}: "
                 f"{len(self.named)} named, {len(self.omitted)} omitted"]
        for delta in self.omitted:
            lines.append(f"  OMITTED  {delta.path}  ({delta.category})")
        if not self.omitted:
            lines.append("  every addition this release made is named in its own entry")
        return "\n".join(lines)


def coverage(repository: str | Path, *, version: str, baseline: str,
             revision: str = "HEAD", changelog: str | None = None) -> Coverage:
    """Which of this release's additions its changelog entry names, and which not."""
    text = changelog if changelog is not None else (
        Path(repository) / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = entry_for(text, version)
    named, omitted = [], []
    for delta in additions(repository, baseline=baseline, revision=revision):
        (named if _names(entry, delta.token) else omitted).append(delta)
    return Coverage(version=version, baseline=baseline,
                    named=tuple(named), omitted=tuple(omitted))


def _cli(argv: list[str]) -> int:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        prog="release_delta.py",
        description="Whether a release's changelog entry accounts for what it changed.")
    parser.add_argument("repository", nargs="?", default=".")
    parser.add_argument("--version", help="defaults to the manifest's version")
    parser.add_argument("--baseline", required=True, help="the revision this release follows")
    parser.add_argument("--revision", default="HEAD")
    arguments = parser.parse_args(argv)

    version = arguments.version
    if not version:
        manifest = json.loads(
            (Path(arguments.repository) / "PACK_MANIFEST.json").read_text(encoding="utf-8"))
        version = manifest["version"]
    try:
        report = coverage(arguments.repository, version=version,
                          baseline=arguments.baseline, revision=arguments.revision)
    except (ValueError, RuntimeError) as exc:
        print(f"DELTA NOT ESTABLISHED: {exc}")
        return 1
    print(report.render())
    print("DELTA COMPLETE" if report.complete else "DELTA INCOMPLETE")
    return 0 if report.complete else 1


if __name__ == "__main__":
    import sys as _sys

    from errors import run_cli
    from release_delta import _cli as _entry

    raise SystemExit(run_cli(_entry, _sys.argv[1:]))
