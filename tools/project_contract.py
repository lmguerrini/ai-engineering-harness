"""The project contract, read by the tools that enforce it.

Every declaration a checker needs — the private vocabulary, the workspace
classification, the paths whose content is exempt — is written once in
`PROJECT.yaml` and was, until now, retyped as a command-line flag at every
application point. A verdict that depends on flags a human retyped is a verdict
that can be obtained twice with different answers, and it was: the same scanner
over the same range reported `clean` and `7 leak(s)` depending on whether the
caller remembered to pass the defaults.

So this module exists to make the contract the single source. `--project` beats
`--term` for the same reason a compiler beats a style guide.

**It fails loud, and that is the whole design.** A configuration reader that
returns an empty set when it cannot parse its input reproduces exactly the
failure it was written to prevent — a gate that scanned nothing and said so in
no way a reader could see. Every parse problem raises. A block that is required
for the requested purpose and is absent raises. There is no path through this
module that turns "I could not read the declaration" into "the declaration was
empty".

The parser accepts the subset of YAML the contract template actually uses:
nested block mappings at two-space indent, block and flow sequences, comments,
quoted or bare scalars, **block scalars** (`|` and `>`, with `-` and `+`
chomping), and a flow sequence spanning several lines. Anything else raises
rather than being guessed at. A full YAML implementation is deliberately not
imported — the toolbelt is import-closed to the standard library
(`DECISIONS.md` D3), so a checker keeps working in an environment where nothing
has been installed.

RP2.2 added the multi-line forms because their absence was a defect, not a
scoping decision: every one of them raised `unexpected indentation`, so a
project could not write a multi-line description in the one file D10 makes the
single source for every gate. They were verified against a reference YAML
implementation across the full cross-product of style, chomping indicator and
body shape — as an oracle during development, never as a dependency.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
import os
from pathlib import Path

from errors import GateRefusal
from instrument import read_rule

__all__ = [
    "ContractError",
    "ProjectContract",
    "parse_yaml_subset",
    "DEFAULT_TERMS_RELATIVE",
    "PUBLICATION_INTENTS",
]

#: Where the pack's own default vocabulary lives, relative to the pack root.
DEFAULT_TERMS_RELATIVE = "policy/private-terms.default.json"

#: What a project says it is for. `internal` is a first-class answer, not an
#: omission: a project that will never be published should not be walked through
#: publication ceremony because Core can perform it.
PUBLICATION_INTENTS = ("internal", "public")

_COMMENT = re.compile(r"(?:^|\s)#.*$")
_KEY = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*)\s*:(?:\s+(?P<value>.*))?$")
_ITEM = re.compile(r"^-(?:\s+(?P<value>.*))?$")


class ContractError(GateRefusal):
    """The contract could not be read, or does not say what was asked of it.

    A **refusal**, in the toolbelt's own hierarchy, rather than a bare
    `Exception`. It was the second: `errors.run_cli` catches `HxError` and this
    was outside it, so a project whose contract declared a requirement nothing
    checks got a stack trace instead of the refusal that was written for it.
    Found by an independent audit, which also found that the structural test
    guarding the wrapper could not see it.
    """

    code = "HX_CONTRACT"


def _strip_comment(line: str) -> str:
    """Remove a trailing comment, honouring quotes.

    A `#` inside a quoted scalar is data. The template's own patterns contain
    `#` in neither position today, but a path pattern legitimately can, and a
    stripper that does not know about quotes silently truncates a declaration
    — which is the failure mode this whole module exists to refuse.
    """
    out: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(line):
        character = line[index]
        if quote:
            # Inside a DOUBLE-quoted scalar a backslash escapes the next
            # character, including the closing quote. Tracking quotes without
            # that made `"q\\"inside"` look unterminated and refused a valid
            # document — fail-closed, and still wrong. A single-quoted scalar
            # has no backslash escape; there `''` is the doubled-quote form and
            # is handled where the scalar is read.
            if quote == '"' and character == "\\" and index + 1 < len(line):
                out.append(character)
                out.append(line[index + 1])
                index += 2
                continue
            out.append(character)
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
            out.append(character)
        elif character == "#" and (not out or out[-1].isspace()):
            break
        else:
            out.append(character)
        index += 1
    if quote:
        raise ContractError(f"unterminated {quote} quote in {line!r}")
    return "".join(out).rstrip()


def _escaped_close(text: str) -> bool:
    """Whether a double-quoted scalar's closing quote is itself escaped."""
    if text[0] != '"':
        return False
    backslashes = 0
    index = len(text) - 2
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def _scalar(raw: str) -> object:
    """One YAML scalar, in the forms the contract template uses."""
    text = raw.strip()
    if not text:
        return None
    if text[0] in "&*":
        # An anchor or an alias. The module promises to raise rather than guess,
        # and it was guessing: `a: &x 1` parsed to the string `'&x 1'`, which is
        # a value nobody wrote. Found by an independent audit.
        raise ContractError(
            f"YAML anchors and aliases are not in the supported subset: {raw!r}"
        )
    if text[0] in "\"'":
        if len(text) < 2 or text[-1] != text[0] or _escaped_close(text):
            raise ContractError(f"unterminated quoted scalar {raw!r}")
        inner = text[1:-1]
        # In a single-quoted YAML scalar, `''` is one literal quote.
        if text[0] == "'":
            return inner.replace("''", "'")
        return _double_quoted(inner, raw)
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


#: The escape sequences a YAML double-quoted scalar defines. Anything else is
#: refused rather than passed through — this module's stated policy, and the
#: reason it matters here is not stylistic.
#:
#: Returning the raw text was a **silent mis-parse with a leak behind it**. A
#: project declaring `project_patterns: ["\\bAcmeSecret\\b"]` — the ordinary way
#: to write a regex in double quotes — got the two-character sequence
#: backslash-b, which compiles to a literal `b` preceded by a backslash and
#: matches nothing. The declared rule applied to every surface and found
#: nothing, and the scan reported clean. That is the founding defect of this
#: whole toolbelt, reintroduced through the parser. Found by an independent
#: audit, reproduced end to end through the real gate.
_DOUBLE_QUOTE_ESCAPES = {
    "0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v",
    "f": "\f", "r": "\r", "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\",
    "N": "\x85", "_": "\xa0", "L": "\u2028", "P": "\u2029",
}


def _double_quoted(inner: str, raw: str) -> str:
    """A double-quoted scalar with its escapes resolved, or a stated failure."""
    out: list[str] = []
    index = 0
    while index < len(inner):
        character = inner[index]
        if character != "\\":
            out.append(character)
            index += 1
            continue
        if index + 1 >= len(inner):
            raise ContractError(f"trailing backslash in double-quoted scalar {raw!r}")
        following = inner[index + 1]
        if following in _DOUBLE_QUOTE_ESCAPES:
            out.append(_DOUBLE_QUOTE_ESCAPES[following])
            index += 2
            continue
        if following in ("x", "u", "U"):
            width = {"x": 2, "u": 4, "U": 8}[following]
            digits = inner[index + 2:index + 2 + width]
            if len(digits) != width or any(d not in "0123456789abcdefABCDEF" for d in digits):
                raise ContractError(
                    f"malformed \\{following} escape in double-quoted scalar {raw!r}"
                )
            out.append(chr(int(digits, 16)))
            index += 2 + width
            continue
        raise ContractError(
            f"unknown escape \\{following} in double-quoted scalar {raw!r}; this parser "
            "resolves the escapes YAML defines and refuses the rest rather than passing "
            "them through as text"
        )
    return "".join(out)


def _flow_sequence(raw: str) -> list[object]:
    """A `[a, b, c]` sequence. Nested flow collections are refused, not guessed."""
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    if "[" in inner or "{" in inner:
        raise ContractError(f"nested flow collections are not supported: {raw!r}")
    items: list[object] = []
    for part in _split_flow(inner):
        items.append(_scalar(part))
    return items


def _split_flow(inner: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for character in inner:
        if quote:
            current.append(character)
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
            current.append(character)
        elif character == ",":
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
    if quote:
        raise ContractError("unterminated quote in flow sequence")
    parts.append("".join(current))
    return [part for part in (p.strip() for p in parts) if part]


@dataclass
class _Line:
    indent: int
    text: str
    number: int
    #: A block scalar's resolved text, when this line opened one. Carried here
    #: because a block scalar's body is *content* — a `#` in it is a hash, a
    #: blank line is a blank line, and its indentation is data — so it cannot
    #: survive the comment-stripping and blank-skipping the scanner applies to
    #: structural lines. It is resolved once, during scanning, and the mapping
    #: parser reads it instead of re-deriving it.
    block: str | None = None


#: `|`, `>`, and their chomping indicators. An explicit indentation indicator
#: (`|2`) is refused by name rather than mis-read: it is rare, and guessing at
#: it would produce a scalar that is *nearly* right, which is worse here than a
#: refusal.
_BLOCK_HEADER = re.compile(r"^(?P<style>[|>])(?P<chomp>[+-]?)$")
_BLOCK_HEADER_WITH_INDENT = re.compile(r"^[|>][+-]?\d+[+-]?$|^[|>]\d")


def _resolve_block(style: str, chomp: str, body: list[str]) -> str:
    """A block scalar's text, from its already-dedented body lines.

    Trailing blank lines are separated from content first, because all three
    chomping indicators are defined in terms of them: `-` drops every trailing
    break, `+` keeps every one, and the default clips them to exactly one.
    """
    content = _rstrip_blank(body)
    trailing = len(body) - len(content)

    if not content:
        return "\n" * trailing if chomp == "+" else ""

    if style == "|":
        text = "\n".join(content)
    else:
        # Folded. A single break between two non-empty lines becomes a space; a
        # run of blank lines becomes that many newlines; and a *more indented*
        # line keeps its breaks, which is the rule that lets a folded scalar
        # carry anything with structure in it.
        pieces: list[str] = []
        for line in content:
            if not line.strip():
                pieces.append("\n")
            elif line[:1].isspace():
                pieces.append("\n" + line + "\n")
            elif pieces and not pieces[-1].endswith("\n"):
                pieces.append(" " + line)
            else:
                pieces.append(line)
        text = "".join(pieces).rstrip("\n")

    if chomp == "-":
        return text
    if chomp == "+":
        return text + "\n" * (1 + trailing)
    return text + "\n"


def _rstrip_blank(body: list[str]) -> list[str]:
    """``body`` up to and including its last line with content."""
    end = len(body)
    while end and not body[end - 1].strip():
        end -= 1
    return body[:end]


def _significant_lines(document: str) -> list[_Line]:
    """The document's structural lines, with block scalars already resolved.

    RP2.2 (CA-AMD-6): every form of valid multi-line data raised
    `unexpected indentation` — `|`, `>`, `|-`, `|+`, and a flow sequence spanning
    lines. Reproduced by execution. The reader was fail-closed about it, which is
    the right direction and still wrong: a project cannot write a multi-line
    description in the one file every gate reads, and `D10` makes that file the
    single source. Repaired here rather than by importing a YAML library, because
    the toolbelt is import-closed to the standard library (`DECISIONS.md` D3) and
    a checker has to keep working where nothing has been installed.
    """
    raw_lines = document.splitlines()
    lines: list[_Line] = []
    index = 0
    while index < len(raw_lines):
        raw = raw_lines[index]
        number = index + 1
        if raw.strip().startswith("#"):
            index += 1
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ContractError(f"line {number}: tab in indentation")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            index += 1
            continue

        indent = len(stripped) - len(stripped.lstrip())
        text = stripped.strip()
        index += 1

        # A sequence item may open a block scalar on its own line: `- goal: |`.
        # `_KEY` never matches a `- ` line, so the header was invisible and the
        # refusal told the author to write the very form they had written.
        # Found by an independent audit.
        item = _ITEM.match(text)
        key_text, item_offset = (item.group("value") or "", indent + 2) if item else (text, indent)
        match = _KEY.match(key_text) if key_text else None
        value = match.group("value").strip() if match and match.group("value") else ""

        if value and _BLOCK_HEADER_WITH_INDENT.match(value):
            raise ContractError(
                f"line {number}: an explicit block indentation indicator ({value!r}) is not "
                "supported; write the block at a consistent indent instead"
            )

        header = _BLOCK_HEADER.match(value) if value else None
        if header:
            # The block belongs to the key, so it ends at the key's own indent —
            # which inside a sequence item is the column after the dash, not the
            # dash's own. Passing the dash's indent swallowed the item's next key.
            body, index = _block_body(raw_lines, index, item_offset if item else indent, number)
            resolved = _resolve_block(header.group("style"), header.group("chomp"), body)
            if item:
                # Re-emit as the sequence item it is: the dash line, then the
                # key at the item's own indent, so the sequence parser sees the
                # shape it already understands.
                lines.append(_Line(indent, "-", number))
                lines.append(_Line(item_offset, f"{match.group('key')}:", number, block=resolved))
            else:
                lines.append(_Line(indent, f"{match.group('key')}:", number, block=resolved))
            continue

        if value.startswith("[") and not value.endswith("]"):
            text, index = _continue_flow(raw_lines, index, text, number)

        lines.append(_Line(indent, text, number))
    return lines


def _block_body(
    raw_lines: list[str], index: int, key_indent: int, opened_at: int
) -> tuple[list[str], int]:
    """The dedented body of a block scalar, and the line after it.

    Read from the **raw** lines: inside a block scalar a `#` is a hash and a
    blank line is a blank line, so neither comment-stripping nor blank-skipping
    may touch them.
    """
    body: list[str] = []
    block_indent: int | None = None
    while index < len(raw_lines):
        raw = raw_lines[index]
        if not raw.strip():
            body.append("")
            index += 1
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= key_indent:
            break
        if block_indent is None:
            block_indent = indent
        if indent < block_indent:
            raise ContractError(
                f"line {index + 1}: this line is less indented than the block scalar "
                f"opened on line {opened_at}, which ended it ambiguously"
            )
        body.append(raw[block_indent:])
        index += 1
    if block_indent is None:
        # `key: |` with nothing under it but blank lines. An empty block is an
        # empty string, which is a value — not the absence of one. The blanks
        # are still returned, because `+` chomping counts them and discarding
        # them made `|+` with an all-blank body yield `''` where it should
        # yield the newlines. Found by an independent audit.
        return body, index
    return body, index


def _continue_flow(
    raw_lines: list[str], index: int, text: str, opened_at: int
) -> tuple[str, int]:
    """Join a `[...]` flow sequence that spans lines into one logical line."""
    depth = text.count("[") - text.count("]")
    while depth > 0 and index < len(raw_lines):
        piece = _strip_comment(raw_lines[index]).strip()
        index += 1
        if not piece:
            continue
        text = f"{text} {piece}"
        depth += piece.count("[") - piece.count("]")
    if depth > 0:
        raise ContractError(f"line {opened_at}: unterminated flow sequence")
    return text, index


def parse_yaml_subset(document: str) -> dict:
    """Parse the block-mapping subset the contract template uses.

    Raises :class:`ContractError` on anything outside that subset. It does not
    fall back, coerce, or skip: an unreadable declaration must not arrive at a
    gate as an empty one.
    """
    lines = _significant_lines(document)
    value, index = _parse_block(lines, 0, lines[0].indent if lines else 0)
    if index != len(lines):
        raise ContractError(f"line {lines[index].number}: unexpected indentation")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ContractError("the project contract must be a mapping at the top level")
    return value


def _parse_block(lines: list[_Line], index: int, indent: int) -> tuple[object, int]:
    if index >= len(lines):
        return None, index
    if _ITEM.match(lines[index].text):
        return _parse_sequence(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines: list[_Line], index: int, indent: int) -> tuple[dict, int]:
    mapping: dict = {}
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ContractError(
                f"line {line.number}: unexpected indentation. If this is a continued "
                "value, write it as a block scalar (`key: |` for literal lines, "
                "`key: >` for folded); a plain scalar continued across lines is not "
                "in the supported subset because it cannot be told apart from this "
                "being a typo"
            )
        match = _KEY.match(line.text)
        if not match:
            raise ContractError(f"line {line.number}: expected 'key:', found {line.text!r}")
        key = match.group("key")
        if key in mapping:
            # Two declarations of one key is a contract defect. Taking the last
            # silently is how a project ends up enforcing a rule it does not
            # believe it declared.
            raise ContractError(f"line {line.number}: duplicate key {key!r}")
        raw_value = match.group("value")
        block = line.block
        index += 1
        if block is not None:
            # Resolved during scanning, where the body was still intact.
            mapping[key] = block
            continue
        if raw_value:
            stripped = raw_value.strip()
            if stripped.startswith("["):
                if not stripped.endswith("]"):
                    raise ContractError(f"line {line.number}: unterminated flow sequence")
                mapping[key] = _flow_sequence(stripped)
            elif stripped.startswith("{"):
                raise ContractError(f"line {line.number}: flow mappings are not supported")
            else:
                mapping[key] = _scalar(stripped)
            continue
        if index < len(lines) and lines[index].indent > line.indent:
            child, index = _parse_block(lines, index, lines[index].indent)
            mapping[key] = child
        elif index < len(lines) and lines[index].indent == line.indent and _ITEM.match(lines[index].text):
            # A block sequence may sit at its parent key's own indent.
            child, index = _parse_sequence(lines, index, line.indent)
            mapping[key] = child
        else:
            mapping[key] = None
    return mapping, index


def _parse_sequence(lines: list[_Line], index: int, indent: int) -> tuple[list, int]:
    items: list = []
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ContractError(f"line {line.number}: unexpected indentation")
        match = _ITEM.match(line.text)
        if not match:
            break
        inline = match.group("value")
        index += 1
        if inline:
            stripped = inline.strip()
            key_match = _KEY.match(stripped)
            if key_match:
                # `- id: value` opens a mapping whose remaining keys are
                # indented to the character after the dash.
                child_indent = line.indent + 2
                block_lines = [_Line(child_indent, stripped, line.number)]
                while index < len(lines) and lines[index].indent >= child_indent:
                    block_lines.append(lines[index])
                    index += 1
                child, consumed = _parse_mapping(block_lines, 0, child_indent)
                if consumed != len(block_lines):
                    raise ContractError(f"line {line.number}: unexpected indentation in sequence item")
                items.append(child)
            elif stripped.startswith("["):
                items.append(_flow_sequence(stripped))
            else:
                items.append(_scalar(stripped))
            continue
        if index < len(lines) and lines[index].indent > line.indent:
            child, index = _parse_block(lines, index, lines[index].indent)
            items.append(child)
        else:
            items.append(None)
    return items, index


def _as_str_list(value: object, *, field: str) -> tuple[str, ...]:
    """A declared list of strings, or a stated failure. Never a silent empty."""
    if value is None:
        return ()
    if isinstance(value, str):
        raise ContractError(
            f"{field} must be a list, not a bare scalar; write [\"{value}\"] or a block sequence"
        )
    if not isinstance(value, list):
        raise ContractError(f"{field} must be a list, found {type(value).__name__}")
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        if not isinstance(item, str):
            raise ContractError(f"{field} entries must be strings, found {item!r}")
        out.append(item)
    return tuple(out)


@dataclass(frozen=True)
class ProjectContract:
    """The declarations the toolbelt enforces, read from one authoritative file."""

    path: Path
    raw: dict
    repo_path: str | None
    release_ref: str | None
    integration_ref: str | None
    project_terms: tuple[str, ...]
    project_patterns: tuple[str, ...]
    default_terms: tuple[str, ...]
    default_identity_terms: tuple[str, ...]
    default_patterns: tuple[str, ...]
    default_identity_patterns: tuple[str, ...]
    optional_pattern_groups: tuple[str, ...]
    safe_generated: tuple[str, ...]
    ignore_private: tuple[str, ...]
    content_exempt: tuple[str, ...]
    must_be_tracked: tuple[str, ...]
    publishable_refs: tuple[str, ...]
    #: Declared executable adapters, parsed. ``None`` means the contract has no
    #: `adapters:` block at all, which is a different statement from an empty
    #: one: "nobody said" against "someone said none". A caller that needs the
    #: declaration can refuse the first and accept the second.
    adapters: tuple | None = ()
    #: The declared Project Context, parsed. ``None`` means the contract has no
    #: `project_context:` block, which is a clean state — the project simply has
    #: no semantic authority to consult. Parsed here so a malformed declaration
    #: fails when every other block does, rather than at first use.
    project_context: object | None = None
    #: `internal` or `public`. Decides which PRESENTATION obligations apply and
    #: nothing else: the universal public-safety invariants hold either way,
    #: because private is an access control rather than a property of the
    #: content and access controls change. `None` means the project did not say.
    publication_intent: str | None = None
    #: Per validation profile, the environment it is claimed to run in:
    #: `public_clone`, `developer_machine`, or a name the project defines. A
    #: profile measured only where its larger sibling is already satisfied names
    #: the smaller of two constraints, which is how a limitation came to be
    #: recorded against the wrong environment.
    reproducible_by: tuple[tuple[str, str], ...] = ()
    #: Where the default vocabulary was actually read from, and whether that was
    #: the canonical location. A checker reading a stale copy of its own rule
    #: manufactures findings as readily as a weak one misses them, and the
    #: resolution that produced them used to be invisible in every report.
    default_terms_source: object | None = None

    @classmethod
    def load(cls, path: str | Path, *, pack_root: str | Path | None = None) -> "ProjectContract":
        # ABSOLUTE FROM HERE ON. Everything this class resolves relative to a
        # contract — the repository, an adapter locator — is resolved against
        # `self.path.parent`, and a contract loaded by a relative path (which is
        # exactly how a CLI invoked from the project loads one) left that parent
        # relative too. The same object then answered differently from two
        # working directories. Found by an independent reader of the repair that
        # was supposed to close this class.
        contract_path = Path(path).resolve()
        if contract_path.is_dir():
            contract_path = contract_path / "PROJECT.yaml"
        try:
            document = contract_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # Bytes that are not UTF-8 are a failure to READ, and `read_text`
            # signals that with a `ValueError` rather than an `OSError`. Without
            # this, a contract with one bad byte reached every `--project` CLI as
            # a traceback, and `open_capability` RAISED instead of reporting,
            # because it catches `ContractError` and this was not one.
            raise ContractError(f"cannot read the project contract at {contract_path}: {exc}") from exc
        raw = parse_yaml_subset(document)

        project = raw.get("project") or {}
        if not isinstance(project, dict):
            raise ContractError("`project:` must be a mapping")

        terms_block = raw.get("private_terms") or {}
        if isinstance(terms_block, list):
            # The pre-2.1 shape, and a real project on this machine still
            # carries it. Every `--project` tool has refused that contract since
            # the schema changed, with a message about a type — so the project
            # was told its file was malformed rather than that it was written to
            # an older generation of the schema, and nothing named the
            # migration. Treated the way an unverifiable legacy pin is: reported
            # at every use, named as legacy, and remedied by migrating rather
            # than by this reader guessing which of the two tiers the entries
            # belonged to. Guessing is the part that would be unsafe — the tiers
            # differ in whether a term is applied to blob content, and reading
            # the older flat list as either one changes what gets scanned.
            raise ContractError(
                "`private_terms:` is a LIST, which is the pre-2.1 schema. This contract has not "
                "been migrated, and no tool has been able to read it since. The current shape is "
                "a mapping:\n"
                "    private_terms:\n"
                "      default_set: policy/private-terms.default.json\n"
                "      project: [ ... this file's current list ... ]\n"
                "      project_patterns: [ ... any `private_patterns:` block ... ]\n"
                "The entries are NOT migrated automatically: the two tiers differ in whether a "
                "term applies to blob content, and choosing for you would change what gets "
                "scanned. See templates/PROJECT.yaml.template."
            )
        if not isinstance(terms_block, dict):
            raise ContractError("`private_terms:` must be a mapping")
        classification = raw.get("workspace_classification") or {}
        if not isinstance(classification, dict):
            raise ContractError("`workspace_classification:` must be a mapping")
        publication = raw.get("publication") or {}
        if not isinstance(publication, dict):
            raise ContractError("`publication:` must be a mapping")

        intent = publication.get("intent")
        if intent is not None and intent not in PUBLICATION_INTENTS:
            raise ContractError(
                f"`publication.intent` is {intent!r}; it is one of {', '.join(PUBLICATION_INTENTS)}. "
                "An intent nothing recognises would decide which obligations apply by accident"
            )
        profiles = raw.get("validation_profiles") or {}
        if not isinstance(profiles, dict):
            raise ContractError("`validation_profiles:` must be a mapping")
        reproducible: list[tuple[str, str]] = []
        for name, block in profiles.items():
            if not isinstance(block, dict):
                continue
            environment = block.get("reproducible_by")
            if environment is None:
                continue
            if not isinstance(environment, str) or not environment.strip():
                raise ContractError(
                    f"`validation_profiles.{name}.reproducible_by` must name an environment"
                )
            reproducible.append((str(name), environment.strip()))

        declared_default = terms_block.get("default_set")
        defaults, default_terms_source = _load_default_terms(declared_default, contract_path, pack_root)

        optional_groups = _as_str_list(
            terms_block.get("optional_pattern_groups"), field="private_terms.optional_pattern_groups"
        )
        selected_optional: list[str] = []
        available = defaults.get("optional_patterns") or {}
        if not isinstance(available, dict):
            raise ContractError("`optional_patterns` in the default term set must be a mapping")
        for group in optional_groups:
            if group not in available:
                raise ContractError(
                    f"private_terms.optional_pattern_groups names {group!r}, which the default "
                    f"set does not define; available: {sorted(available) or 'none'}"
                )
            selected_optional.extend(available[group])

        return cls(
            path=contract_path,
            raw=raw,
            repo_path=_optional_str(project.get("repo_path")),
            release_ref=_optional_str(project.get("release_ref")),
            integration_ref=_optional_str(project.get("integration_ref")),
            project_terms=_as_str_list(
                terms_block.get("project_additions"), field="private_terms.project_additions"
            ),
            project_patterns=(
                *_as_str_list(terms_block.get("project_patterns"), field="private_terms.project_patterns"),
                *selected_optional,
            ),
            default_terms=tuple(defaults.get("terms") or ()),
            default_identity_terms=tuple(defaults.get("identity_terms") or ()),
            default_patterns=tuple(defaults.get("patterns") or ()),
            default_identity_patterns=tuple(defaults.get("identity_patterns") or ()),
            optional_pattern_groups=optional_groups,
            safe_generated=_as_str_list(
                classification.get("safe_generated"), field="workspace_classification.safe_generated"
            ),
            ignore_private=_as_str_list(
                classification.get("ignore_private"), field="workspace_classification.ignore_private"
            ),
            content_exempt=_as_str_list(
                classification.get("content_exempt"), field="workspace_classification.content_exempt"
            ),
            must_be_tracked=_as_str_list(
                classification.get("must_be_tracked"), field="workspace_classification.must_be_tracked"
            ),
            publishable_refs=_as_str_list(
                publication.get("publishable_refs"), field="publication.publishable_refs"
            ),
            adapters=_load_adapters(raw),
            project_context=_load_project_context(raw, contract_path),
            default_terms_source=default_terms_source,
            publication_intent=intent,
            reproducible_by=tuple(reproducible),
        )

    def repository(self, override: str | None = None) -> str:
        """The repository these declarations describe.

        **A RELATIVE DECLARATION IS RELATIVE TO THE CONTRACT, never to the
        process.** This returned `repo_path` verbatim, so every caller that falls back to a
        RELATIVE declaration (`commit_gate --range`, `outgoing_scan`, `workspace_report`,
        `publication_gate`, `publication_history`) ran against whatever
        repository the invoking shell happened to be standing in. Two projects on
        one machine resolved to one repository and it was neither of theirs;
        found in this release by rendering the multiproject history view over two
        adopting projects and reading the coordinator's own commit count under
        both of their names.

        Resolved here rather than at each caller because the callers cannot each
        be relied on to remember, and the seventh one has not been written yet.
        An override still wins, and an absolute declaration is returned as
        declared.
        """
        if override:
            return override
        if not self.repo_path:
            raise ContractError(
                f"{self.path} declares no project.repo_path, so the repository must be given explicitly"
            )
        declared = Path(self.repo_path)
        if declared.is_absolute():
            return self.repo_path
        # JOINED, AND OTHERWISE ONLY WHAT `Path` DOES. An absolute declaration is
        # returned verbatim precisely so nothing rewrites a path the project
        # chose; the relative branch does the one thing it must — make it
        # absolute against the contract. `Path` still tidies a trailing separator
        # and a doubled one (`link/` and `./link//` both become `link`), which a
        # bounded reading noted, and which changes no destination.
        #
        # TWO WRONG ANSWERS PRECEDED THIS ONE. `.resolve()` follows symlinks, so
        # it rewrote a declaration made through a link while the absolute branch
        # preserved it: two answers to one question, and a reader showed a mutant
        # dropping the call survived, so neither behaviour was pinned.
        # `os.path.normpath` then collapsed `..` LEXICALLY, before the filesystem
        # interpreted the link — so `link/..`, where `link` points into another
        # tree, named the contract's own directory instead of the link's parent.
        # A bounded reading of that repair found it. The filesystem resolves both
        # correctly when the path is used; this returns what the project wrote,
        # rooted where the project wrote it.
        return str(self.path.parent / declared)


def _load_adapters(raw: dict) -> tuple | None:
    """The declared adapters, parsed at load so a malformed one raises here.

    Imported lazily: `adapter_pin` reads a contract when run as a CLI, and a
    module-level import in both directions is a cycle. The parse still happens
    during `load`, so an unreadable adapters block fails at the same moment
    every other unreadable block does (D10) rather than at first use.
    """
    if "adapters" not in raw:
        return None
    import adapter_pin

    try:
        return adapter_pin.declarations_from(raw.get("adapters"))
    except adapter_pin.IntegrityError as exc:
        raise ContractError(f"{exc.cause}" + "".join(
            f"; {key}: {value}" for key, value in sorted(exc.detail.items())
        )) from exc


def _load_project_context(raw: dict, contract_path: Path) -> object | None:
    """The declared Project Context, parsed at load like every other block.

    Lazily imported for the same reason `adapter_pin` is: `project_context`
    reads a contract from its own CLI, and a module-level import in both
    directions is a cycle.
    """
    if "project_context" not in raw:
        return None
    import project_context

    try:
        return project_context.declaration_from(
            raw.get("project_context"), declared_in=contract_path.parent)
    except project_context.ContextError as exc:
        raise ContractError(str(exc)) from exc


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContractError(f"expected a string, found {value!r}")
    return value or None


def _load_default_terms(
    declared: object, contract_path: Path, pack_root: str | Path | None
) -> tuple[dict, object]:
    """The pack's default vocabulary, the file it came from, or a stated failure.

    `private_terms.default_set` is a path relative to the pack root. A project
    that omits it still gets the defaults: the whole point of EC-H is that
    forgetting to name the default set must not silently disable it.
    """
    relative = DEFAULT_TERMS_RELATIVE
    if declared is not None:
        if not isinstance(declared, str):
            raise ContractError("private_terms.default_set must be a path")
        relative = declared

    #: The root the rule must come from. A declared pack root is the project's
    #: own statement of where its governance lives; absent one, the pack this
    #: module ships inside is the only root there is.
    canonical_root = Path(pack_root) if pack_root else Path(__file__).resolve().parent.parent

    candidates: list[Path] = []
    declared_path = Path(relative)
    if declared_path.is_absolute():
        candidates.append(declared_path)
    else:
        candidates.append(canonical_root / relative)
        # Kept as a SEARCHED location rather than a usable one. Before RP2.3 a
        # copy beside the contract was a silent fallback: a project that
        # declared a pack root whose rule was missing got whichever file the
        # order reached next, applied its terms, and reported only how many
        # there were. Listing it here means the refusal can say what else was
        # on the path.
        candidates.append(contract_path.parent / relative)

    try:
        content, source = read_rule(candidates, canonical_root=canonical_root, what="default term set")
    except GateRefusal as exc:
        raise ContractError(
            f"the default term set {relative!r} could not be resolved from the canonical root. "
            f"{exc.render()} A scan without the default vocabulary is not a scan the pack can "
            f"vouch for, and a scan with somebody else's copy of it is worse."
        ) from exc

    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContractError(f"cannot read the default term set at {source.path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"the default term set at {source.path} must be a JSON object")
    return data, source
