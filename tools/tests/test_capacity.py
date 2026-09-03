"""The wave that lost eighty-one records, and the rules that refuse it.

The safety assertion is not that the arithmetic is right. It is that **authority
does not move under resource pressure** and that an unmeasurable window produces
caution rather than either a fabricated number or a deadlock.
"""

import pytest

import capacity
from capacity import (
    UNKNOWN,
    AuthorityClass,
    Dispatch,
    Pool,
    PoolKind,
    Reserve,
    Verdict,
    WindowKind,
)
from errors import IntegrityError, PreconditionError


def _dispatch(**overrides):
    fields = dict(task_id="t1", pool_id="p1", authority_class=AuthorityClass.AUTHORITY_FREE,
                  allowed_executor_class="bounded-implementer")
    fields.update(overrides)
    return Dispatch(**fields)


def _pool(**overrides):
    # Dated by default. A numeric reading with no `observed_at` is refused, and
    # a fixture that had to restate the timestamp in twenty places would push
    # every test to omit it — which is how the field went unenforced in the
    # first place. Its absence is proven refused by its own test below.
    fields = dict(pool_id="p1", observed_at="2026-09-03T12:00:00Z")
    fields.update(overrides)
    return Pool(**fields)


# --- authority, which is checked before any arithmetic ---------------------------


def test_a_dispatch_that_does_not_state_its_authority_class_is_refused():
    """A precondition, not a field. The rule was once asserted with nothing on a
    task to hang it on, so its rehearsal could only pass on a hand-labelled
    fixture."""
    with pytest.raises(PreconditionError) as caught:
        Dispatch(task_id="t", pool_id="p", allowed_executor_class="x")
    assert "attaches to the TASK" in caught.value.render()


def test_a_task_carrying_a_decision_is_never_rerouted_however_much_capacity_says():
    """The safety assertion of this whole module. A fixture in which a product
    decision is offered to whichever route is still answering must be refused,
    not rerouted."""
    decision = capacity.gate(
        _dispatch(authority_class=AuthorityClass.CARRIES_AUTHORITY,
                  allowed_executor_class="the-coordinator",
                  allowed_fallback_routes=("anything-else",),
                  reroute_to="anything-else", estimated_cost=1),
        _pool(remaining=1_000_000, kind=PoolKind.INDEPENDENT),
        Reserve(coordinator=1, result_consumption=1, repair_and_audit=1),
    )
    assert decision.verdict == Verdict.REFUSE
    assert "Authority attaches to the TASK" in decision.why
    assert not decision.may_dispatch


def test_an_authority_free_task_may_reroute_only_among_its_declared_routes():
    permitted = capacity.gate(
        _dispatch(allowed_fallback_routes=("independent-worker",), reroute_to="independent-worker",
                  estimated_cost=1, result_consumption_cost=1),
        _pool(remaining=100, kind=PoolKind.INDEPENDENT),
        Reserve(coordinator=1, result_consumption=1, repair_and_audit=1),
    )
    assert permitted.verdict == Verdict.DISPATCH

    refused = capacity.gate(
        _dispatch(allowed_fallback_routes=("independent-worker",), reroute_to="somebody-else",
                  estimated_cost=1),
        _pool(remaining=100), Reserve(coordinator=1, result_consumption=1, repair_and_audit=1),
    )
    assert refused.verdict == Verdict.REFUSE
    assert "nobody recorded" in refused.why


def test_wait_versus_spend_is_named_as_a_human_row_rather_than_answered():
    decision = capacity.wait_or_spend(_dispatch(), _pool(resets_at="in four hours"))
    assert decision.verdict == Verdict.ESCALATE_ROW_15
    assert "row 15" in decision.why


# --- the arithmetic, where everything is known -----------------------------------


def test_a_dispatch_that_would_leave_less_than_the_declared_reserve_is_refused():
    decision = capacity.gate(
        _dispatch(estimated_cost=90),
        _pool(remaining=100, kind=PoolKind.INDEPENDENT),
        Reserve(coordinator=20, result_consumption=5, repair_and_audit=5),
    )
    assert decision.verdict == Verdict.REFUSE
    assert "Continuation safety outranks utilisation" in decision.why


def test_a_dispatch_the_window_cannot_hold_at_all_names_the_reset():
    decision = capacity.gate(
        _dispatch(estimated_cost=500),
        _pool(remaining=100, resets_at="2026-09-03T18:00Z", kind=PoolKind.INDEPENDENT),
        Reserve(coordinator=1, result_consumption=1, repair_and_audit=1),
    )
    assert decision.verdict == Verdict.REFUSE_UNTIL_RESET
    assert "2026-09-03T18:00Z" in decision.render()


def test_a_result_that_could_not_be_read_before_exhaustion_is_negative_return():
    """The negative control the rehearsal names: producing a result nobody can
    consume costs everything the production cost and returns nothing."""
    decision = capacity.gate(
        _dispatch(estimated_cost=50, result_consumption_cost=45),
        _pool(remaining=100, kind=PoolKind.INDEPENDENT),
        Reserve(coordinator=10, result_consumption=0, repair_and_audit=0),
    )
    assert decision.verdict == Verdict.REFUSE
    assert "work nobody can consume is work nobody did" in decision.why


def test_a_dispatch_that_fits_is_permitted_and_says_what_would_remain():
    decision = capacity.gate(
        _dispatch(estimated_cost=10, result_consumption_cost=5),
        _pool(remaining=100, unit="requests", kind=PoolKind.INDEPENDENT),
        Reserve(coordinator=10, result_consumption=5, repair_and_audit=5),
    )
    assert decision.verdict == Verdict.DISPATCH
    assert "90 requests" in decision.why


# --- the shared window, which is the measured failure -------------------------------


def test_a_second_dispatch_on_the_coordinators_own_window_is_serialised():
    """Eight in two waves on one shared window returned two results and lost
    eighty-one records."""
    decision = capacity.gate(
        _dispatch(estimated_cost=1, result_consumption_cost=1),
        _pool(remaining=1000, kind=PoolKind.SHARED_WITH_COORDINATOR, active_workers=1),
        Reserve(coordinator=1, result_consumption=1, repair_and_audit=1),
    )
    assert decision.verdict == Verdict.DISPATCH_SERIALLY
    assert "eighty-one records" in decision.why


def test_an_independent_pool_is_not_serialised_by_the_same_rule():
    """The distinction that made the recovery routing work. A rule that
    serialised everything would refuse correct work."""
    decision = capacity.gate(
        _dispatch(estimated_cost=1, result_consumption_cost=1),
        _pool(remaining=1000, kind=PoolKind.INDEPENDENT, active_workers=3),
        Reserve(coordinator=1, result_consumption=1, repair_and_audit=1),
    )
    assert decision.verdict == Verdict.DISPATCH


# --- unknown, which is first-class ----------------------------------------------------


def test_an_unmeasurable_window_produces_caution_rather_than_a_number():
    """One of the two providers in the evidence base had no machine-readable
    capacity surface at all. A gate that cannot represent that will invent a
    number."""
    decision = capacity.gate(_dispatch(), _pool(remaining=UNKNOWN), Reserve())
    assert decision.verdict == Verdict.DISPATCH_SERIALLY
    assert decision.may_dispatch, "a gate that deadlocks on absent telemetry gets routed around"
    assert "how much of pool p1 remains" in decision.unknowns
    assert "the reserve this project holds back" in decision.unknowns


def test_an_unmeasurable_window_refuses_a_second_concurrent_dispatch():
    """Serial is the whole permission. Fanning out on a window nobody can
    measure is the exact shape of the measured loss."""
    decision = capacity.gate(_dispatch(), _pool(remaining=UNKNOWN, active_workers=1), Reserve())
    assert decision.verdict == Verdict.REFUSE
    assert not decision.may_dispatch


def test_every_unestablished_quantity_is_named_rather_than_defaulted():
    decision = capacity.gate(_dispatch(), _pool(), Reserve())
    assert set(decision.unknowns) == {
        "how much of pool p1 remains",
        "whether this pool is shared with the coordinator",
        "the reserve this project holds back",
        "what this dispatch would cost",
        "what reading the result would cost",
    }


def test_a_partially_declared_reserve_makes_the_total_unknown_rather_than_smaller():
    """Three reserves, spent at three different moments. Two of three known is
    not a total, and treating it as one silently lowers the floor."""
    reserve = Reserve(coordinator=10, result_consumption=5)
    assert reserve.total == UNKNOWN and not reserve.declared


def test_a_quantity_that_is_not_a_quantity_is_refused_rather_than_coerced():
    for bad in (-1, True, "12"):
        with pytest.raises(IntegrityError):
            Pool(pool_id="p", remaining=bad)
        with pytest.raises(IntegrityError):
            Reserve(coordinator=bad)


def test_no_universal_reserve_is_built_in_anywhere():
    """A number that fits one provider's window is wrong for another's, and a
    wrong one fails in both directions. Asserted structurally so a later
    convenience cannot add one."""
    default = Reserve()
    assert (default.coordinator, default.result_consumption, default.repair_and_audit) == (
        UNKNOWN, UNKNOWN, UNKNOWN)
    assert Pool(pool_id="p").remaining == UNKNOWN


# --- the module holds nothing --------------------------------------------------------


def test_this_module_has_no_dispatch_verb_and_no_queue():
    """The frozen record forbids a scheduler, and a queue that later drains is
    a scheduler however it is described. Structural, so a later convenience
    cannot quietly add one."""
    names = set(dir(capacity))
    for forbidden in ("dispatch_now", "enqueue", "queue", "run", "submit", "schedule",
                      "pending", "drain"):
        assert forbidden not in names, f"capacity gained {forbidden!r}"
    assert set(capacity.__all__) >= {"gate", "Decision", "Verdict"}


def test_a_dispatch_measured_against_the_wrong_pool_is_refused_loudly():
    with pytest.raises(IntegrityError):
        capacity.gate(_dispatch(pool_id="p1"), _pool(pool_id="p2"), Reserve())


def test_a_decision_produces_an_outcome_rather_than_merely_naming_a_vocabulary():
    """The first version of this test compared the class's own tuple with a
    literal copy of it — an assertion that would have passed unchanged if the
    mechanism it named were deleted, because there was no mechanism. Found by an
    independent auditor. What is asserted now is that a decision PRODUCES one."""
    refused = capacity.gate(
        _dispatch(estimated_cost=99),
        _pool(remaining=1, kind=PoolKind.INDEPENDENT),
        Reserve(coordinator=1, result_consumption=1, repair_and_audit=1))
    assert not refused.may_dispatch
    assert refused.outcome == capacity.DispatchOutcome.NOT_DISPATCHED
    assert "NOT_DISPATCHED" in refused.render()

    permitted = capacity.gate(
        _dispatch(estimated_cost=1, result_consumption_cost=1),
        _pool(remaining=100, kind=PoolKind.INDEPENDENT),
        Reserve(coordinator=1, result_consumption=1, repair_and_audit=1))
    assert permitted.outcome == capacity.DispatchOutcome.IN_FLIGHT, (
        "a permitted dispatch has not succeeded yet; calling it consumed here is the conflation "
        "the four states exist to prevent"
    )
    assert permitted.outcome != capacity.DispatchOutcome.NOT_DISPATCHED


def test_the_two_outcomes_a_gate_cannot_produce_are_the_ones_a_runner_records():
    """`DISPATCHED_AND_CONSUMED` and `DISPATCHED_AND_LOST` are produced by
    whoever ran the work, not by the gate that permitted it — which is why they
    are different parties at different times."""
    from_gate = {
        capacity.gate(_dispatch(estimated_cost=c, result_consumption_cost=1),
                      _pool(remaining=100, kind=PoolKind.INDEPENDENT),
                      Reserve(coordinator=1, result_consumption=1, repair_and_audit=1)).outcome
        for c in (1, 999)
    }
    assert from_gate == {capacity.DispatchOutcome.IN_FLIGHT,
                         capacity.DispatchOutcome.NOT_DISPATCHED}
    assert capacity.DispatchOutcome.DISPATCHED_AND_LOST not in from_gate


def test_an_unknown_pool_kind_is_refused_by_name():
    with pytest.raises(IntegrityError) as caught:
        Pool(pool_id="p", kind="probably-fine")
    assert PoolKind.SHARED_WITH_COORDINATOR in caught.value.render()


# --- the command line ------------------------------------------------------------------


def test_the_cli_exit_status_separates_permitted_refused_and_human(capsys):
    base = ["t", "--pool", "p", "--authority", AuthorityClass.AUTHORITY_FREE,
            "--executor", "bounded", "--observed-at", "2026-09-03T12:00:00Z"]

    assert capacity._cli(base + ["--remaining", "100", "--cost", "1", "--consumption-cost", "1",
                                 "--reserve-coordinator", "1", "--reserve-consumption", "1",
                                 "--reserve-repair", "1", "--kind", PoolKind.INDEPENDENT]) == 0
    assert Verdict.DISPATCH in capsys.readouterr().out

    assert capacity._cli(base + ["--remaining", "10", "--cost", "9",
                                 "--reserve-coordinator", "5", "--reserve-consumption", "0",
                                 "--reserve-repair", "0"]) == 1
    assert Verdict.REFUSE in capsys.readouterr().out

    assert capacity._cli(base + ["--remaining", "UNKNOWN"]) == 0
    assert Verdict.DISPATCH_SERIALLY in capsys.readouterr().out

    # A reading with no moment is reported as a refusal, not raised as a
    # traceback: a command line that cannot use its input has to say so.
    undated = [a for a in base if a not in ("--observed-at", "2026-09-03T12:00:00Z")]
    assert capacity._cli(undated + ["--remaining", "100"]) == 2
    assert "when it was taken" in capsys.readouterr().out


def test_the_window_kind_vocabulary_covers_rolling_and_longer_windows():
    """Weekly capacity was never the binding constraint and the rolling window
    always was, so a model that cannot express both cannot record why."""
    assert WindowKind.ROLLING in WindowKind.ALL and WindowKind.WEEKLY in WindowKind.ALL
    assert Pool(pool_id="p", window=WindowKind.WEEKLY).window == "weekly"


# --- a number that is not a number ---------------------------------------------
#
# Every comparison against a NaN is false, so `NaN < 0` passed the sign check and
# then `remaining - cost < reserve` was false too: the gate DISPATCHED an
# unmeasurable pool. Found by a cross-vendor auditor. `gitread` already refuses a
# non-finite timeout for exactly this reason and the rule was not carried across.


def test_a_non_finite_quantity_is_refused_rather_than_passing_every_guard():
    import math

    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(IntegrityError) as caught:
            Pool(pool_id="p", remaining=bad)
        assert "every comparison against it is false" in caught.value.render()
        with pytest.raises(IntegrityError):
            Reserve(coordinator=bad)
        with pytest.raises(IntegrityError):
            _dispatch(estimated_cost=bad)


def test_the_reproduction_no_longer_dispatches():
    """The auditor's exact fixture."""
    import math

    with pytest.raises(IntegrityError):
        capacity.gate(
            _dispatch(estimated_cost=1, result_consumption_cost=1),
            _pool(remaining=math.nan, kind=PoolKind.INDEPENDENT),
            Reserve(coordinator=1, result_consumption=1, repair_and_audit=1))


def test_a_numeric_reading_states_when_it_was_taken():
    """The class docstring says `observed_at` matters as much as `remaining`, and
    the class accepted a bare `remaining=100` and gated on it with no unknowns
    recorded. A figure with no age is the one thing that distinguishes a
    measurement from an assertion. Quoted back at it by a blind auditor."""
    with pytest.raises(IntegrityError):
        capacity.Pool(pool_id="p", remaining=100, kind=capacity.PoolKind.INDEPENDENT)

    dated = capacity.Pool(pool_id="p", remaining=100, kind=capacity.PoolKind.INDEPENDENT,
                          observed_at="2026-09-03T12:00:00Z")
    assert dated.remaining == 100
    # UNKNOWN needs no timestamp: it is already the answer for not knowing.
    assert capacity.Pool(pool_id="p", kind=capacity.PoolKind.INDEPENDENT).remaining == capacity.UNKNOWN
