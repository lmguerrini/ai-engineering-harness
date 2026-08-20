"""One containment rule, for every gate that asks where work may land.

There were two. Ingestion normalised a declared path before comparing it;
the lifecycle freeze gate compared the raw string. They agreed on the six cases
somebody thought to write down and disagreed on `src\\loader`, on `./src/loader`,
and on anything else where normalisation is the difference. Both were
fail-closed, so nothing escaped — but "the two gates agree" was recorded as a
closed finding when what had actually happened was that both gates were made
*similar*.

Similar is not the same. A rule with two implementations drifts, and the drift
is invisible precisely because each implementation has tests that pass. So this
module holds the rule once and both callers import it, and a property test
compares nothing because there is nothing to compare.
"""

from __future__ import annotations

import posixpath
import sys

__all__ = ["normalise", "within", "normalise_all"]


def normalise(path: object) -> str | None:
    """A declared path as a repository-relative POSIX path, or ``None``.

    ``None`` means the path cannot be made into a promise about where changes
    land: it is absolute, it climbs out with ``..``, it names a drive, it is
    padded with whitespace, it carries a record separator, or it is not a string
    at all. Refusing is the whole behaviour — a boundary that admits an
    unnormalisable path is not a boundary.

    On record separators specifically: **one argument must denote exactly one
    path.** A candidate containing a newline, carriage return or NUL is refused
    outright, wherever in the string it appears. Stripping the ends is not
    enough — `"src/ok.py\\ntests/evil.py"` normalises to something that starts
    under an allowed root, so an interior separator smuggles a second,
    never-checked path through a single CONTAINED verdict. That is not
    hypothetical: the natural shell invocation
    `git status --porcelain | awk '{print $2}'` produces exactly this blob under
    a shell that does not word-split, and the coordinator wrote it that way on
    the first attempt. POSIX permits these bytes in a filename; a boundary gate
    refuses them anyway, because "refuse when the answer is unclear" is the rule
    that has held.
    """
    if not isinstance(path, str) or not path or path != path.strip() or path.startswith(("/", "\\")):
        return None
    if any(separator in path for separator in ("\n", "\r", "\x00")):
        return None
    converted = path.replace("\\", "/")
    normal = posixpath.normpath(converted)
    if normal in (".", "..") or normal.startswith("../") or ":" in normal.split("/", 1)[0]:
        return None
    return normal.rstrip("/")


def normalise_all(paths: object) -> tuple[tuple[str, ...], tuple[object, ...]]:
    """Normalise a declared list, returning what worked and what did not."""
    if not isinstance(paths, (list, tuple)):
        return (), (paths,)
    normalised = [(item, normalise(item)) for item in paths]
    good = tuple(value for _item, value in normalised if value is not None)
    bad = tuple(item for item, value in normalised if value is None)
    return good, bad


def within(path: str, root: str) -> bool:
    """Whether a normalised path lies inside a normalised root.

    Both arguments are expected to have been through `normalise`. Case is
    significant, because it is significant to the filesystems this runs against
    and to Git; treating `SRC/` and `src/` as the same root would admit work
    outside the declared boundary on a case-sensitive checkout.
    """
    return path == root or path.startswith(root + "/")


def _cli(argv: list[str]) -> int:
    """Report contained/refused for each candidate path against declared roots.

    Usage: ``scope_check.py --allow ROOT [--allow ROOT ...] -- CANDIDATE...``

    Exits non-zero if any candidate is refused (unnormalisable, or outside
    every declared root), or if a declared root itself does not normalise.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="scope_check.py",
        description="Report whether candidate paths are contained within declared allowed roots.",
    )
    parser.add_argument("--allow", action="append", default=[], metavar="ROOT", help="a declared allowed root (repeatable)")
    parser.add_argument("candidates", nargs="+", metavar="PATH", help="candidate paths to check")
    args = parser.parse_args(argv)

    roots, bad_roots = normalise_all(args.allow)
    if bad_roots:
        for root in bad_roots:
            print(f"REFUSED (bad root declaration): {root!r}")
        return 2

    refused = False
    for candidate in args.candidates:
        normal = normalise(candidate)
        if normal is None:
            print(f"REFUSED: {candidate!r} (does not normalise to a repository-relative path)")
            refused = True
            continue
        if any(within(normal, root) for root in roots):
            print(f"CONTAINED: {candidate!r} -> {normal!r}")
        else:
            print(f"REFUSED: {candidate!r} -> {normal!r} (outside every declared root)")
            refused = True

    return 1 if refused else 0


if __name__ == "__main__":
    import sys

    from errors import run_cli

    raise SystemExit(run_cli(_cli, sys.argv[1:]))
