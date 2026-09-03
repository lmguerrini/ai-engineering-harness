"""Durable output a task owns, written in bounded pieces, recovered before retry.

`skills/core/worker-contract.md` already requires a dispatched worker to write
its findings to a durable file. That is necessary and it is not sufficient, and
the gap cost real work twice, in two different ways:

*   **One atomic write, too large to land.** A worker produced a complete
    result, tried to return it in one piece, exceeded the provider's output
    limit, and left **no durable artifact at all**. The file's absence looks
    identical whether the worker never started or finished and could not
    deliver. Worst-case loss on that dispatch: 27 records. Rewritten as three
    files of nine, one per write, in index order: worst-case loss 9.

*   **A wave that lost most of itself.** Eight workers dispatched, three
    returned nothing, 81 records gone. Three of six killed workers had
    nevertheless left usable bytes on disk, and one had written a complete
    generator it never executed — 22 records recovered by running it. Nothing
    looked, because the retry decision was taken from the worker's status label
    rather than from the artifacts.

So the property is not *write to a fixed path*. It is **write in bounded
increments, in order, never hold completed work back, and classify from the
artifacts before deciding what to retry.**

## The four answers, and why two is not enough

    COMPLETED_WITH_DURABLE_OUTPUT       consume it; do not re-run
    FAILED_WITH_PARTIAL_DURABLE_OUTPUT  resume from the first missing piece
    FAILED_BEFORE_USEFUL_OUTPUT         re-dispatch whole
    UNKNOWN                             classify before acting; never auto-resolve

A two-valued classifier — *did it finish?* — discards the third case, and the
third case is where the recovered 22 records were. `UNKNOWN` is not a catch-all
either: it is earned by a specific inconsistency (a gap in the index, a
completion marker that disagrees with what is on disk, bytes the contract does
not describe) and it never resolves itself, because auto-resolving an unknown is
how one piece of work enters history twice.

## What this module does and does not do

It does not write a worker's output for it. A dispatched worker is another
vendor's process and will not import this. What Core owns is the part that has
to be the same for every worker: the **contract**, the **clause that puts it in
the brief** in a form recoverable without asking the worker, the **ownership of
the output root**, and the **classification and resume decision afterwards**.

`materialise` exists for producers that *are* in this process — the pack's own
rehearsals among them — and writes through the same `.part`-then-rename protocol
the brief clause describes, so the fixtures exercise the protocol rather than a
convenient imitation of it.

**A task owns its output root.** Hand-authored content inside a directory a
generator owns is not stored, it is cached: a destructive rebuild destroyed two
hand-written documents, and the rebuild was correct. So a root under a declared
generated tree is refused, and a root another task has claimed is refused.

**This module does not know whether the chunk size is right.** That number comes
from the provider's output limit and the per-record cost, both adapter facts
that change. It requires that a bound be declared, refuses a write that exceeds
it, and classifies a root holding an over-bound chunk as `UNKNOWN` — because a
producer that ignored the contract is a producer whose output this cannot vouch
for. It has no opinion on the value itself.
"""

from __future__ import annotations


import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pathmatch
from errors import IntegrityError, PreconditionError
from instrument import Examined

__all__ = [
    "OutputContract",
    "RecoveryState",
    "RecoveryReport",
    "ResumePlan",
    "OWNER_MARKER",
    "COMPLETION_MARKER",
    "CHUNK_DIRECTORY",
    "PART_SUFFIX",
    "claim_root",
    "materialise",
    "classify",
    "resume_plan",
    "brief_clause",
]

#: Names the task that owns this root. Written once, checked before every
#: dispatch: a root two tasks write into is a root neither can be recovered
#: from, and the marker is how a stateless checker can tell.
OWNER_MARKER = "TASK-OWNER.json"

#: Written by the producer after the last chunk lands, and only then. Its
#: presence is a claim the classifier checks against the chunks rather than
#: believes.
COMPLETION_MARKER = "COMPLETE.json"

#: Chunks live in their own directory so that other declared products of the
#: task — a generator, a log, an index — cannot be mistaken for them.
CHUNK_DIRECTORY = "chunks"

#: A chunk being written. Renamed onto its final name when, and only when, it is
#: complete. Rename within a directory is atomic on every filesystem this pack
#: supports, which is what makes "killed mid-chunk" cost exactly that chunk.
PART_SUFFIX = ".part"

_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CHUNK_NAME = re.compile(r"^(?P<index>\d{4})\.(?P<extension>[A-Za-z0-9]{1,16})$")
_PART_NAME = re.compile(r"^(?P<index>\d{4})\.(?P<extension>[A-Za-z0-9]{1,16})\.part$")


class RecoveryState:
    """The four answers. Strings rather than an enum so a report round-trips
    through JSON without a decoder, and so a record written today is readable by
    a reader that does not import this module."""

    COMPLETED_WITH_DURABLE_OUTPUT = "COMPLETED_WITH_DURABLE_OUTPUT"
    FAILED_WITH_PARTIAL_DURABLE_OUTPUT = "FAILED_WITH_PARTIAL_DURABLE_OUTPUT"
    FAILED_BEFORE_USEFUL_OUTPUT = "FAILED_BEFORE_USEFUL_OUTPUT"
    UNKNOWN = "UNKNOWN"

    ALL = (
        COMPLETED_WITH_DURABLE_OUTPUT,
        FAILED_WITH_PARTIAL_DURABLE_OUTPUT,
        FAILED_BEFORE_USEFUL_OUTPUT,
        UNKNOWN,
    )


@dataclass(frozen=True)
class OutputContract:
    """What a dispatched task declares about its output, before it is dispatched.

    Every field is required to be *derivable from the brief alone*, because the
    recovery path runs when the worker is gone. A scheme only the worker knows
    is a scheme nobody can recover from.
    """

    task_id: str
    output_root: Path
    #: Bytes per INDIVIDUAL write. Derived by the caller from the provider's
    #: output limit and the per-record cost; this module requires that one
    #: exists and that what landed honours it, and has no opinion on the value.
    max_bytes_per_write: int
    chunk_extension: str = "json"
    #: How many chunks the task expects to produce, when that is knowable from
    #: the brief. `None` is a legitimate answer and is not a missing field: a
    #: task that cannot know its own length in advance says so, and the
    #: completion marker is then the only thing that closes it.
    expected_chunks: int | None = None
    #: Other durable products this task may leave — a generator it wrote, an
    #: index, a log. Relative to the root. Their presence with no chunks is the
    #: case a two-valued classifier discards and the one that recovered 22
    #: records.
    products: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _TASK_ID.fullmatch(self.task_id or ""):
            raise IntegrityError(
                "a task id must be a short, stable, filesystem-safe name",
                task_id=repr(self.task_id),
            )
        if not isinstance(self.max_bytes_per_write, int) or isinstance(self.max_bytes_per_write, bool):
            raise IntegrityError("max_bytes_per_write must be a whole number of bytes",
                                 value=repr(self.max_bytes_per_write))
        if self.max_bytes_per_write <= 0:
            # The negative control from the rehearsal plan: a brief that invites
            # one unbounded write is refused BEFORE dispatch, because that is
            # the failure that happened.
            raise PreconditionError(
                "a task that does not bound an individual write is a task whose output limit "
                "failure costs everything; the bound is derived from the provider's output "
                "limit and the per-record cost, and it is stated in the brief",
                task_id=self.task_id,
                declared=self.max_bytes_per_write,
            )
        if not re.fullmatch(r"[A-Za-z0-9]{1,16}", self.chunk_extension or ""):
            raise IntegrityError("a chunk extension must be short and alphanumeric",
                                 extension=repr(self.chunk_extension))
        if self.expected_chunks is not None:
            if (not isinstance(self.expected_chunks, int) or isinstance(self.expected_chunks, bool)
                    or self.expected_chunks < 1):
                raise IntegrityError("expected_chunks is a count of at least one, or nothing at all",
                                     value=repr(self.expected_chunks))
        object.__setattr__(self, "output_root", Path(self.output_root))

    # --- the paths, derived rather than remembered ---------------------------

    @property
    def chunk_root(self) -> Path:
        return self.output_root / CHUNK_DIRECTORY

    def chunk_path(self, index: int) -> Path:
        """``chunks/0007.json``. Zero-padded so lexical order is index order —
        a recovery pass that sorted `10` before `2` would resume from the wrong
        place and call the gap a completion."""
        if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index > 9999:
            raise IntegrityError("a chunk index is a whole number from 0 to 9999", index=repr(index))
        return self.chunk_root / f"{index:04d}.{self.chunk_extension}"

    def part_path(self, index: int) -> Path:
        return self.chunk_path(index).with_name(self.chunk_path(index).name + PART_SUFFIX)


# --- owning the root -------------------------------------------------------------


def claim_root(
    contract: OutputContract,
    *,
    generated_paths: Sequence[str] = (),
    relative_to: str | Path | None = None,
) -> Path:
    """Create the output root and record which task owns it, or refuse.

    Two refusals, both measured:

    *   **A root under a tree a generator owns.** Hand-authored content there is
        cached rather than stored, and a destructive rebuild — which was itself
        correct — destroyed two documents. The declaration is the project's
        (`workspace_classification`), so it is passed in rather than guessed.
    *   **A root another task already owns.** Two tasks interleaving chunk
        indices in one directory produce a sequence neither of them can be
        recovered from, and the marker is how a stateless checker sees it.
    """
    root = contract.output_root
    if generated_paths:
        base = Path(relative_to) if relative_to else Path.cwd()
        try:
            relative = root.resolve().relative_to(Path(base).resolve())
        except ValueError:
            relative = None
        if relative is not None and pathmatch.matches_any(str(relative), list(generated_paths)):
            raise PreconditionError(
                "a task output root may not sit inside a tree a generator owns; content there "
                "is cached rather than stored, and a correct destructive rebuild destroys it",
                root=str(root),
                declared_generated=", ".join(generated_paths),
            )

    marker = root / OWNER_MARKER
    if marker.exists():
        try:
            recorded = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PreconditionError("the output root's owner marker cannot be read",
                                    root=str(root), error=str(exc)) from exc
        owner = recorded.get("task_id")
        if owner != contract.task_id:
            raise PreconditionError(
                "this output root is owned by another task; two tasks writing one chunk "
                "sequence produce a sequence neither can be recovered from",
                root=str(root), owned_by=repr(owner), claiming=contract.task_id,
            )
        return root

    contract.chunk_root.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {
                "task_id": contract.task_id,
                "chunk_extension": contract.chunk_extension,
                "max_bytes_per_write": contract.max_bytes_per_write,
                "expected_chunks": contract.expected_chunks,
                "products": list(contract.products),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return root


# --- writing one piece -------------------------------------------------------------


def materialise(contract: OutputContract, index: int, data: bytes | str) -> Path:
    """Write one chunk so that a kill costs at most this chunk.

    Written to `<name>.part`, flushed, and only then renamed onto its final
    name. A process killed before the rename leaves a `.part` the classifier
    reads as *this index was in progress*; one killed after it leaves a
    complete chunk. There is no third state, which is the whole point: the
    difference between the two is one rename, and rename is atomic.

    For producers inside this process. A dispatched worker follows the same
    protocol from the brief clause, because it is another vendor's process and
    will not import this.
    """
    payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    if len(payload) > contract.max_bytes_per_write:
        raise PreconditionError(
            "this write exceeds the bound the task declared, which is the failure that "
            "produced no durable artifact at all",
            task_id=contract.task_id, index=index,
            bytes=len(payload), bound=contract.max_bytes_per_write,
        )
    final = contract.chunk_path(index)
    part = contract.part_path(index)
    part.parent.mkdir(parents=True, exist_ok=True)
    with open(part, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(part, final)
    return final


def complete(contract: OutputContract, chunk_count: int) -> Path:
    """Record that the task finished, and how many chunks it says it wrote.

    The count is a *claim*. `classify` compares it with what is on disk and
    answers `UNKNOWN` when they disagree, because a completion marker over a
    short sequence is exactly the shape a truncated run leaves.
    """
    marker = contract.output_root / COMPLETION_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"task_id": contract.task_id, "chunk_count": chunk_count}, indent=2) + "\n",
        encoding="utf-8",
    )
    return marker


# --- reading what is there ------------------------------------------------------


@dataclass(frozen=True)
class RecoveryReport:
    """What the artifacts say, and nothing the worker said about itself."""

    task_id: str
    state: str
    #: Complete chunk indices, in order.
    complete: tuple[int, ...] = ()
    #: Indices missing from an otherwise present sequence. Any gap is `UNKNOWN`:
    #: resuming past one silently drops the work it stands for.
    gaps: tuple[int, ...] = ()
    #: The index a `.part` was found for, if any. At most one is expected; more
    #: than one means two producers, which is `UNKNOWN`.
    partial: tuple[int, ...] = ()
    #: Declared products present on disk. A task with these and no chunks has
    #: left useful work, and this is the case a two-valued classifier discards.
    products: tuple[str, ...] = ()
    #: Bytes the contract does not describe. Never ignored: an unexplained file
    #: in a task-owned root is either a second writer or a scheme the recovery
    #: path does not understand, and both are `UNKNOWN`.
    undescribed: tuple[str, ...] = ()
    #: Chunks that landed over the declared bound. The producer did not honour
    #: the contract this classification reads, so whether those bytes are whole
    #: is not decidable from here — which makes it `UNKNOWN` rather than a note
    #: beside a clean verdict. An auditor obtained
    #: `COMPLETED_WITH_DURABLE_OUTPUT` over three chunks fifty times the bound.
    over_bound: tuple[int, ...] = ()
    #: What the completion marker claimed, if one was present and readable.
    claimed_count: int | None = None
    #: A completion marker that exists and cannot be read. Distinct from absent,
    #: because a claim nobody can check is not the same as no claim.
    marker_unreadable: bool = False
    why: str = ""

    @property
    def examined(self) -> Examined:
        return Examined({
            "complete chunks": len(self.complete),
            "partial chunks": len(self.partial),
            "other products": len(self.products),
        })

    def render(self) -> str:
        lines = [f"task {self.task_id}: {self.state}", f"  {self.why}"]
        lines.append(f"  examined: {self.examined.summary()}")
        if self.complete:
            lines.append(f"  complete chunks: {self.complete[0]}..{self.complete[-1]}")
        for label, values in (("gaps in the sequence", self.gaps), ("in progress", self.partial),
                              ("over the declared bound", self.over_bound)):
            if values:
                lines.append(f"  {label}: {', '.join(str(v) for v in values)}")
        for label, values in (("products", self.products), ("NOT DESCRIBED BY THE CONTRACT", self.undescribed)):
            if values:
                lines.append(f"  {label}: {', '.join(values)}")
        return "\n".join(lines)


def _contiguous(indices: Sequence[int]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """``(present, gaps)`` where gaps are the indices missing below the highest."""
    present = tuple(sorted(set(indices)))
    if not present:
        return (), ()
    expected = set(range(present[-1] + 1))
    return present, tuple(sorted(expected - set(present)))


def classify(contract: OutputContract) -> RecoveryReport:
    """One of four answers, read from the artifacts and from nothing else.

    Never from a worker's status label. Three of six killed workers reported
    failure and had left usable bytes; one had written a complete generator it
    never ran. The label and the disk disagreed, and the disk was right.
    """
    root = contract.output_root
    if not root.is_dir():
        return RecoveryReport(
            task_id=contract.task_id, state=RecoveryState.FAILED_BEFORE_USEFUL_OUTPUT,
            why="the output root does not exist, so nothing was ever materialised",
        )

    # WHOSE OUTPUT THIS IS, asked before anything is read out of it.
    #
    # `claim_root` refuses to claim a root another task owns — and `classify`
    # never asked, so a contract for `beta` pointed at `alpha`'s finished root
    # reported `beta COMPLETED_WITH_DURABLE_OUTPUT` and handed alpha's work over
    # as beta's. Found by a blind auditor. The marker was already being written
    # for exactly this and only the writer was reading it.
    #
    # UNKNOWN rather than a refusal: a mismatched owner is a real state of the
    # disk that a person resolves, and `resume_plan` already refuses to act on
    # UNKNOWN, so this cannot become a retry.
    marker = root / OWNER_MARKER
    # A SYMLINK IS NOT THIS ROOT'S MARKER. `is_file()` follows one, so a link
    # pointing at a marker elsewhere that named `beta` let beta read alpha's
    # finished work — the same defect as before, wearing the one shape the
    # previous repair's check could not see. Found by a blind reader.
    if marker.is_symlink() or not marker.is_file():
        # ABSENT IS NOT PERMISSION. The first repair asked the marker only when
        # there was one, so deleting it — or replacing it with a directory —
        # restored the defect exactly, and a blind reader did both. An
        # unclaimed root's owner is unknown, and unknown is the answer.
        return RecoveryReport(
            task_id=contract.task_id, state=RecoveryState.UNKNOWN,
            why=(f"this root carries no readable {OWNER_MARKER}, so whose work it holds cannot "
                 f"be established; an output root is claimed before it is written to"),
        )
    if True:
        try:
            # `.get` on whatever JSON happens to hold: `null` and `[]` each
            # raised a bare AttributeError out of a function whose contract is
            # a four-valued state. A marker is an object with a task id, and
            # anything else is a marker nobody can read.
            document = json.loads(marker.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError(f"the marker holds {type(document).__name__}, not an object")
            recorded = document.get("task_id")
            if not isinstance(recorded, str) or not recorded.strip():
                raise ValueError(f"the marker names {recorded!r} as its task")
        except (OSError, ValueError) as exc:
            return RecoveryReport(
                task_id=contract.task_id, state=RecoveryState.UNKNOWN,
                why=f"the output root's owner marker cannot be read, so whose work this is "
                    f"cannot be established: {exc}",
            )
        if recorded != contract.task_id:
            return RecoveryReport(
                task_id=contract.task_id, state=RecoveryState.UNKNOWN,
                why=f"this root is owned by {recorded!r} and the contract is for "
                    f"{contract.task_id!r}; another task's durable output is not this task's "
                    f"result, however complete it looks",
            )

    complete_indices: list[int] = []
    partial_indices: list[int] = []
    over_bound: list[int] = []
    undescribed: list[str] = []

    if contract.chunk_root.is_dir():
        for entry in sorted(contract.chunk_root.iterdir()):
            if not entry.is_file():
                undescribed.append(f"{CHUNK_DIRECTORY}/{entry.name}")
                continue
            chunk = _CHUNK_NAME.fullmatch(entry.name)
            part = _PART_NAME.fullmatch(entry.name)
            if chunk and chunk.group("extension") == contract.chunk_extension:
                index = int(chunk.group("index"))
                complete_indices.append(index)
                if entry.stat().st_size > contract.max_bytes_per_write:
                    over_bound.append(index)
            elif part and part.group("extension") == contract.chunk_extension:
                partial_indices.append(int(part.group("index")))
            else:
                undescribed.append(f"{CHUNK_DIRECTORY}/{entry.name}")

    described = {OWNER_MARKER, COMPLETION_MARKER, CHUNK_DIRECTORY}
    products_present: list[str] = []
    for entry in sorted(root.iterdir()):
        if entry.name in described:
            continue
        relative = entry.name
        if pathmatch.matches_any(relative, list(contract.products)) or relative in contract.products:
            products_present.append(relative)
        else:
            undescribed.append(relative)

    claimed: int | None = None
    marker_unreadable = False
    marker = root / COMPLETION_MARKER
    if marker.is_file():
        try:
            claimed = int(json.loads(marker.read_text(encoding="utf-8"))["chunk_count"])
        except (OSError, ValueError, KeyError, TypeError):
            # Present and unreadable. Recorded as its own fact rather than as a
            # negative count in a field labelled `chunk_count`: a sentinel in a
            # field a reader will treat as a number is the shape this pack
            # refuses everywhere else.
            claimed, marker_unreadable = None, True

    present, gaps = _contiguous(complete_indices)
    common = dict(
        task_id=contract.task_id, complete=present, gaps=gaps,
        partial=tuple(sorted(partial_indices)), products=tuple(products_present),
        undescribed=tuple(undescribed), over_bound=tuple(sorted(over_bound)),
        claimed_count=claimed, marker_unreadable=marker_unreadable,
    )

    # --- UNKNOWN, and every reason for it is specific -----------------------
    if undescribed:
        return RecoveryReport(**common, state=RecoveryState.UNKNOWN, why=(
            "the root holds bytes the contract does not describe, which is either a second "
            "writer or a scheme this recovery path does not understand"))
    if gaps:
        return RecoveryReport(**common, state=RecoveryState.UNKNOWN, why=(
            "the chunk sequence has a gap; resuming past it would silently drop the work it "
            "stands for, and treating it as complete would ship a hole"))
    if len(common["partial"]) > 1:
        return RecoveryReport(**common, state=RecoveryState.UNKNOWN, why=(
            "more than one chunk is in progress, which means more than one producer wrote here"))
    if common["partial"] and (claimed is not None or marker_unreadable):
        return RecoveryReport(**common, state=RecoveryState.UNKNOWN, why=(
            "a completion marker is present and a chunk is still in progress; the task's own "
            "claim that it finished and the bytes on disk disagree, and consuming this would "
            "consume a sequence with a hole in it"))
    if common["over_bound"]:
        return RecoveryReport(**common, state=RecoveryState.UNKNOWN, why=(
            f"chunk(s) {', '.join(str(i) for i in common['over_bound'])} exceed the bound the "
            "task declared, so the producer did not honour the contract this classification "
            "reads; whether those bytes are whole is not decidable from here"))
    if marker_unreadable:
        return RecoveryReport(**common, state=RecoveryState.UNKNOWN, why=(
            "a completion marker is present and unreadable, so the task's own claim about "
            "how much it wrote cannot be checked"))
    if claimed is not None:
        if claimed != len(present):
            return RecoveryReport(**common, state=RecoveryState.UNKNOWN, why=(
                f"the completion marker claims {claimed} chunk(s) and {len(present)} are on "
                f"disk; a marker over a short sequence is what a truncated run leaves"))
        if contract.expected_chunks is not None and claimed != contract.expected_chunks:
            return RecoveryReport(**common, state=RecoveryState.UNKNOWN, why=(
                f"the task declared {contract.expected_chunks} chunk(s) in its brief and its "
                f"completion marker claims {claimed}"))
        return RecoveryReport(**common, state=RecoveryState.COMPLETED_WITH_DURABLE_OUTPUT, why=(
            "every declared chunk is on disk and the completion marker agrees with it"))

    if present or common["partial"] or products_present:
        return RecoveryReport(**common, state=RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT, why=(
            "durable output exists and no completion marker does; consume or resume from it "
            "before re-dispatching anything"))

    return RecoveryReport(**common, state=RecoveryState.FAILED_BEFORE_USEFUL_OUTPUT, why=(
        "the root was claimed and nothing was ever materialised in it"))


# --- deciding what to do next ------------------------------------------------------


@dataclass(frozen=True)
class ResumePlan:
    task_id: str
    action: str
    resume_from: int | None
    keep: tuple[int, ...] = ()
    why: str = ""

    def render(self) -> str:
        line = f"task {self.task_id}: {self.action}"
        if self.resume_from is not None:
            line += f" from chunk {self.resume_from:04d}"
        return f"{line}\n  {self.why}"


def resume_plan(report: RecoveryReport) -> ResumePlan:
    """What a retry may do, given what is already on disk.

    The rule the rehearsal must be able to fail: **a re-dispatch never repeats a
    completed chunk.** A plan that restarts from zero over existing complete
    work is not a safe default, it is the duplicate-work failure with a tidier
    name.

    `UNKNOWN` produces no plan. It produces a refusal, because the whole reason
    the state exists is that acting on it is what turns an ambiguity into two
    copies of one piece of work.
    """
    if report.state == RecoveryState.UNKNOWN:
        raise PreconditionError(
            "an unknown recovery state is classified by a person before anything is retried; "
            "auto-resolving it is how one task acquires two workers",
            task_id=report.task_id, why=report.why,
        )
    if report.state == RecoveryState.COMPLETED_WITH_DURABLE_OUTPUT:
        return ResumePlan(task_id=report.task_id, action="CONSUME", resume_from=None,
                          keep=report.complete,
                          why="the work is done and on disk; re-running it would replace a "
                              "result with an equivalent result at full cost")
    if report.state == RecoveryState.FAILED_BEFORE_USEFUL_OUTPUT:
        return ResumePlan(task_id=report.task_id, action="RE-DISPATCH WHOLE", resume_from=0,
                          why="nothing durable exists, so nothing is repeated by starting over")

    next_index = (report.complete[-1] + 1) if report.complete else 0
    return ResumePlan(
        task_id=report.task_id, action="RESUME", resume_from=next_index, keep=report.complete,
        why=(f"{len(report.complete)} chunk(s) are complete and must not be produced again; "
             f"the interrupted piece is at most one chunk of work"),
    )


# --- the clause that goes in the brief ---------------------------------------------


def brief_clause(contract: OutputContract) -> str:
    """The output contract, in the words the worker is given.

    Every fact the recovery path needs is here, because the recovery path runs
    when the worker is gone: a scheme only the worker knows is a scheme nobody
    can recover from. This is the artifact the rule actually travels in — the
    worker is another vendor's process and will never import this module.
    """
    expected = (
        f"{contract.expected_chunks}" if contract.expected_chunks is not None
        else "as many as the work needs; you do not have to know in advance"
    )
    products = (
        "\n".join(f"  - {name}" for name in contract.products)
        if contract.products else "  - none declared"
    )
    return f"""OUTPUT CONTRACT — read this before you begin, and follow it even if you finish early.

Your output root is:            {contract.output_root}
Write chunks into:              {contract.output_root / CHUNK_DIRECTORY}
Name each chunk:                NNNN.{contract.chunk_extension}   (zero-padded, starting at 0000, no gaps)
Chunks expected:                {expected}
Maximum bytes per single write: {contract.max_bytes_per_write}

How to write one chunk, and this part is not optional:

  1. write it to NNNN.{contract.chunk_extension}{PART_SUFFIX}
  2. finish writing it completely
  3. rename it to NNNN.{contract.chunk_extension}

Renaming last is what makes an interruption cost one chunk instead of
everything. A file still named `{PART_SUFFIX}` is read as "this piece was in
progress"; one without it is read as complete and will not be produced again.

**Materialise each chunk as soon as it is finished.** Completed work you are
holding to send at the end is unrecovered work. If you are stopped, whatever
you have already renamed survives and whatever you were holding does not.

**Never exceed the byte bound on a single write.** A write too large to land
produces no artifact at all, and its absence looks exactly like never having
started.

**Your final message is a report ABOUT the output, never the output.** Say which
chunk indices you completed, what is in them, and anything you could not do.
Do not repeat the content: it is already on disk, and putting it in the message
is the write that does not land.

Other durable products you may leave in the root:
{products}

If you are resuming, the indices already present are complete. Do not rewrite
them; begin at the first index that is absent.
"""


def _cli(argv: list[str]) -> int:
    """Classify a task's durable output, or print the clause its brief needs.

    Usage: ``task_output.py ROOT --task ID --max-bytes N [--expect N]
                            [--extension EXT] [--product NAME ...] [--brief]``

    Without ``--brief`` it reads the root and prints one of the four recovery
    states with the plan that state earns. Exit status follows the state rather
    than a notion of success: ``0`` consume, ``1`` resume or re-dispatch, ``2``
    unknown — because an unknown is a verdict nobody reached, not a failure.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="task_output.py",
        description="Classify a dispatched task's durable output from the artifacts.",
    )
    parser.add_argument("root", help="the task's output root")
    parser.add_argument("--task", required=True, help="the task id that owns the root")
    parser.add_argument("--max-bytes", type=int, required=True, metavar="N",
                        help="bytes per individual write, from the provider's output limit")
    parser.add_argument("--extension", default="json", help="chunk file extension")
    parser.add_argument("--expect", type=int, default=None, metavar="N",
                        help="chunks expected, when the brief can know")
    parser.add_argument("--product", action="append", default=[], metavar="NAME",
                        help="another durable product the task may leave (repeatable)")
    parser.add_argument("--brief", action="store_true",
                        help="print the output-contract clause for the worker's brief")
    args = parser.parse_args(argv)

    contract = OutputContract(
        task_id=args.task, output_root=Path(args.root), max_bytes_per_write=args.max_bytes,
        chunk_extension=args.extension, expected_chunks=args.expect,
        products=tuple(args.product),
    )
    if args.brief:
        print(brief_clause(contract))
        return 0

    report = classify(contract)
    print(report.render())
    if report.state == RecoveryState.UNKNOWN:
        # Deliberately not printed as a plan. The state exists because acting on
        # it is what turns an ambiguity into two copies of one piece of work.
        return 2
    print(resume_plan(report).render())
    return 0 if report.state == RecoveryState.COMPLETED_WITH_DURABLE_OUTPUT else 1


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. Imported
    # statically, by name, because a dynamic import would route around the
    # toolbelt's import-closure check.
    from errors import run_cli
    from task_output import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
