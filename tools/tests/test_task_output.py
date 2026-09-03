"""The four recovery answers, and the retry each one earns.

The fixtures are the measured failures, not invented ones: a worker killed at a
chunk boundary, a worker killed mid-chunk, a worker that wrote a complete
generator it never executed, and an artifact whose completeness is not decidable
from the artifact. Every test names what it must be able to fail.
"""

import json

import pytest

import task_output
from errors import IntegrityError, PreconditionError
from task_output import OutputContract, RecoveryState


def _contract(tmp_path, **overrides):
    fields = dict(
        task_id="batch-08",
        output_root=tmp_path / "work" / "batch-08",
        max_bytes_per_write=64,
    )
    fields.update(overrides)
    return OutputContract(**fields)


# --- the negative control, before anything is dispatched -----------------------


def test_a_task_that_does_not_bound_a_single_write_is_refused_before_dispatch():
    """The rehearsal's negative control, and the failure that actually happened:
    one write large enough to exceed the output limit produced no artifact at
    all, and its absence looked exactly like never having started."""
    for bound in (0, -1):
        with pytest.raises(PreconditionError) as caught:
            OutputContract(task_id="t", output_root="/tmp/x", max_bytes_per_write=bound)
        assert "costs everything" in caught.value.render()


def test_a_write_over_the_declared_bound_is_refused_rather_than_truncated(tmp_path):
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    with pytest.raises(PreconditionError):
        task_output.materialise(contract, 0, "x" * 65)
    # And nothing was left behind that a later pass could mistake for progress.
    assert not contract.chunk_path(0).exists()
    assert not contract.part_path(0).exists()


def test_a_task_id_that_could_not_name_a_directory_is_refused():
    for bad in ("", "../escape", "a/b", "x" * 65):
        with pytest.raises(IntegrityError):
            OutputContract(task_id=bad, output_root="/tmp/x", max_bytes_per_write=10)


# --- who owns the root ----------------------------------------------------------


def test_a_root_inside_a_tree_a_generator_owns_is_refused(tmp_path):
    """Hand-authored content in a generator-owned directory is cached, not
    stored: a destructive rebuild destroyed two hand-written documents, and the
    rebuild was correct."""
    contract = _contract(tmp_path, output_root=tmp_path / "build" / "batch-08")
    with pytest.raises(PreconditionError) as caught:
        task_output.claim_root(contract, generated_paths=["build/"], relative_to=tmp_path)
    assert "cached rather than stored" in caught.value.render()


def test_a_root_outside_every_generated_tree_is_claimed(tmp_path):
    contract = _contract(tmp_path)
    root = task_output.claim_root(contract, generated_paths=["build/"], relative_to=tmp_path)
    assert (root / task_output.OWNER_MARKER).is_file()
    assert json.loads((root / task_output.OWNER_MARKER).read_text())["task_id"] == "batch-08"


def test_a_second_task_may_not_claim_a_root_the_first_owns(tmp_path):
    """Two tasks interleaving chunk indices in one directory produce a sequence
    neither can be recovered from."""
    first = _contract(tmp_path)
    task_output.claim_root(first)
    second = _contract(tmp_path, task_id="batch-09")
    with pytest.raises(PreconditionError) as caught:
        task_output.claim_root(second)
    assert "batch-08" in caught.value.render() and "batch-09" in caught.value.render()


def test_reclaiming_your_own_root_is_how_a_resume_starts(tmp_path):
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    assert task_output.claim_root(contract) == contract.output_root


# --- (i) killed at a chunk boundary ----------------------------------------------


def test_killed_at_a_chunk_boundary_loses_nothing_and_resumes_at_the_next_index(tmp_path):
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    for index in range(3):
        task_output.materialise(contract, index, json.dumps({"records": index}))

    report = task_output.classify(contract)
    assert report.state == RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT
    assert report.complete == (0, 1, 2)

    plan = task_output.resume_plan(report)
    assert plan.action == "RESUME" and plan.resume_from == 3
    assert plan.keep == (0, 1, 2), "a resume that does not name what to keep can still repeat it"


# --- (ii) killed mid-chunk --------------------------------------------------------


def test_killed_mid_chunk_costs_exactly_that_chunk(tmp_path):
    """The `.part` is what a process killed before the rename leaves. There is
    no third state between "in progress" and "complete", and that is what bounds
    the loss at one chunk."""
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "first")
    task_output.materialise(contract, 1, "second")
    contract.part_path(2).write_text("half a chunk")  # killed here

    report = task_output.classify(contract)
    assert report.state == RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT
    assert report.complete == (0, 1) and report.partial == (2,)

    plan = task_output.resume_plan(report)
    assert plan.resume_from == 2, "the interrupted chunk is redone; the complete ones are not"


def test_a_partial_write_never_counts_as_complete(tmp_path):
    """Mutation target for the rename protocol: if a `.part` were read as a
    chunk, a truncated write would be consumed as finished output."""
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    contract.part_path(0).write_text("truncated")
    report = task_output.classify(contract)
    assert report.complete == ()
    assert report.state == RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT


# --- (iii) a complete generator nobody executed -------------------------------------


def test_a_declared_product_with_no_chunks_is_partial_output_not_nothing(tmp_path):
    """The case a two-valued classifier discards, and the one that recovered 22
    records: the worker wrote a complete generator and never ran it. Neither the
    result nor nothing."""
    contract = _contract(tmp_path, products=("generate.py",))
    task_output.claim_root(contract)
    (contract.output_root / "generate.py").write_text("# produces the records\n")

    report = task_output.classify(contract)
    assert report.state == RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT
    assert report.products == ("generate.py",)
    assert "consume or resume" in report.why
    # And it must NOT be re-dispatched whole, which would discard the generator.
    assert task_output.resume_plan(report).action == "RESUME"


# --- (iv) not decidable from the artifact --------------------------------------------


def test_a_gap_in_the_sequence_is_unknown_and_never_resolves_itself(tmp_path):
    """Resuming past a gap silently drops the work it stands for; treating it as
    complete ships a hole. Neither is a decision a checker may take."""
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    for index in (0, 1, 3):
        task_output.materialise(contract, index, f"chunk {index}")

    report = task_output.classify(contract)
    assert report.state == RecoveryState.UNKNOWN and report.gaps == (2,)
    with pytest.raises(PreconditionError) as caught:
        task_output.resume_plan(report)
    assert "two workers" in caught.value.render()


def test_a_completion_marker_that_disagrees_with_the_disk_is_unknown(tmp_path):
    """A marker over a short sequence is exactly what a truncated run leaves."""
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "only one")
    task_output.complete(contract, 5)

    report = task_output.classify(contract)
    assert report.state == RecoveryState.UNKNOWN
    assert "5" in report.why and "1" in report.why


def test_bytes_the_contract_does_not_describe_are_unknown(tmp_path):
    """Either a second writer, or a scheme this recovery path does not
    understand. Both are answers a person gives, not a checker."""
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "a chunk")
    (contract.output_root / "surprise.txt").write_text("who wrote this")

    report = task_output.classify(contract)
    assert report.state == RecoveryState.UNKNOWN
    assert "surprise.txt" in report.undescribed


def test_two_chunks_in_progress_means_two_producers(tmp_path):
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    contract.part_path(0).write_text("one writer")
    contract.part_path(1).write_text("another writer")
    assert task_output.classify(contract).state == RecoveryState.UNKNOWN


def test_an_unreadable_completion_marker_is_unknown_rather_than_ignored(tmp_path):
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "a chunk")
    (contract.output_root / task_output.COMPLETION_MARKER).write_text("{ not json")
    assert task_output.classify(contract).state == RecoveryState.UNKNOWN


def test_a_declared_chunk_count_the_marker_contradicts_is_unknown(tmp_path):
    contract = _contract(tmp_path, expected_chunks=4)
    task_output.claim_root(contract)
    for index in range(2):
        task_output.materialise(contract, index, f"chunk {index}")
    task_output.complete(contract, 2)
    report = task_output.classify(contract)
    assert report.state == RecoveryState.UNKNOWN
    assert "declared 4" in report.why


# --- the completed case, and the retry it must NOT earn -------------------------------


def test_a_completed_task_is_consumed_and_not_re_run(tmp_path):
    contract = _contract(tmp_path, expected_chunks=3)
    task_output.claim_root(contract)
    for index in range(3):
        task_output.materialise(contract, index, f"chunk {index}")
    task_output.complete(contract, 3)

    report = task_output.classify(contract)
    assert report.state == RecoveryState.COMPLETED_WITH_DURABLE_OUTPUT
    plan = task_output.resume_plan(report)
    assert plan.action == "CONSUME" and plan.resume_from is None


def test_no_plan_ever_reproduces_a_chunk_that_is_already_complete(tmp_path):
    """The rule the rehearsal has to be able to fail. A plan that restarts from
    zero over existing complete work is the duplicate-work failure with a
    tidier name, and asserting "nothing was lost" cannot see it."""
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    for index in range(4):
        task_output.materialise(contract, index, f"chunk {index}")

    plan = task_output.resume_plan(task_output.classify(contract))
    assert plan.resume_from is not None
    assert plan.resume_from > max(plan.keep), (
        f"the plan would rewrite chunk {plan.resume_from}, which is already complete"
    )


def test_nothing_at_all_is_a_whole_re_dispatch(tmp_path):
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    report = task_output.classify(contract)
    assert report.state == RecoveryState.FAILED_BEFORE_USEFUL_OUTPUT
    assert task_output.resume_plan(report).action == "RE-DISPATCH WHOLE"


def test_a_root_that_was_never_created_is_not_confused_with_an_empty_one(tmp_path):
    """Both re-dispatch whole, and they are different facts: one task never
    started, the other started and materialised nothing."""
    contract = _contract(tmp_path)
    report = task_output.classify(contract)
    assert report.state == RecoveryState.FAILED_BEFORE_USEFUL_OUTPUT
    assert "does not exist" in report.why


# --- what the worker is actually told ---------------------------------------------------


def test_the_brief_clause_carries_every_fact_the_recovery_path_needs(tmp_path):
    """The recovery path runs when the worker is gone, so a scheme only the
    worker knows is a scheme nobody can recover from. This clause is where the
    rule actually travels — a dispatched worker is another vendor's process and
    will never import this module."""
    contract = _contract(tmp_path, expected_chunks=3, products=("generate.py",))
    clause = task_output.brief_clause(contract)

    assert str(contract.output_root) in clause
    assert f"NNNN.{contract.chunk_extension}" in clause
    assert str(contract.max_bytes_per_write) in clause
    assert task_output.PART_SUFFIX in clause
    assert "rename" in clause.lower()
    assert "report ABOUT the output" in clause
    assert "generate.py" in clause
    assert "3" in clause


def test_the_brief_clause_says_so_when_the_length_is_not_knowable(tmp_path):
    clause = task_output.brief_clause(_contract(tmp_path))
    assert "you do not have to know in advance" in clause


# --- the command line ----------------------------------------------------------------


def test_the_cli_exit_status_follows_the_state_rather_than_a_notion_of_success(tmp_path, capsys):
    contract = _contract(tmp_path)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "a chunk")
    common = [str(contract.output_root), "--task", contract.task_id, "--max-bytes", "64"]

    assert task_output._cli(common) == 1  # partial: resume
    assert "RESUME" in capsys.readouterr().out

    task_output.complete(contract, 1)
    assert task_output._cli(common) == 0  # complete: consume
    assert "CONSUME" in capsys.readouterr().out

    (contract.output_root / "unexplained.txt").write_text("x")
    assert task_output._cli(common) == 2  # unknown: no plan at all
    out = capsys.readouterr().out
    assert RecoveryState.UNKNOWN in out
    assert "RESUME" not in out and "CONSUME" not in out
