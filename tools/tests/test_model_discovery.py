"""Discovery has no vocabulary, and never answers a question it was not asked.

The guarantee under test is negative and structural: a model identifier this pack
has never seen reaches a report without a Core edit. A test that asserted only
"the shipped names are read" would pass against a hard-coded list, so the fixtures
here are deliberately names nothing could have anticipated.
"""

import json

import pytest

import model_discovery
from model_discovery import UNKNOWN, DiscoveryError


def _document(tmp_path, payload, name="discovery.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --- O2: a previously unknown identifier reaches a report ---------------------


@pytest.mark.parametrize("identifier", [
    "gpt-7-synthetic",
    "a-vendor-nobody-has/model-99",
    "модель-7",
    "モデル-9",
    "x.y_z:11+preview",
    "MODEL WITH SPACES",
    "-leading-dash",
    "9",
])
def test_previously_unknown_identifiers_survive_a_reading(tmp_path, identifier):
    """Verbatim, in any alphabet, with no normalisation and no validation.

    A pack that decided which identifiers were well-formed would have invented
    the closed vocabulary it promises not to have.
    """
    document = _document(tmp_path, {"client_version": "9.9.9", "models": [{"slug": identifier}]})
    reading = model_discovery.read(document)
    assert reading.identifiers() == (identifier,)
    assert reading.find(identifier) is not None
    assert "DISCOVERED" in reading.find(identifier).sentence()


def test_no_module_in_the_toolbelt_carries_a_model_vocabulary():
    """The structural half. A list of model names anywhere in the toolbelt is the
    thing this release exists to promise does not exist.

    Searched as a SHAPE rather than as a list of today's names — a check written
    against today's names would age exactly the way the vocabulary it guards
    against ages.
    """
    import pathlib
    import re

    generation = re.compile(r"\b(?:chat)?gpt[\s._-]?\d", re.IGNORECASE)
    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for path in sorted(root.glob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if generation.search(line):
                offenders.append(f"tools/{path.name}:{number}: {line.strip()[:80]}")
    assert not offenders, (
        "a model identifier appears in the toolbelt; discovery must not have a vocabulary:\n  "
        + "\n  ".join(offenders)
    )


# --- discovery is not availability -------------------------------------------


def test_a_reading_claims_only_that_the_document_listed_it(tmp_path):
    document = _document(tmp_path, {"client_version": "1.0.0", "models": [{"slug": "m"}]})
    reading = model_discovery.read(document)
    rendered = reading.render()
    assert "discovery is not availability" in rendered
    assert "DISCOVERED only" in rendered


def test_a_document_written_by_another_client_is_reported_as_skewed(tmp_path):
    """Measured live: a document written by a newer client listed a model the
    installed client could not run, and the installed client's own rewrite did
    not list it at all."""
    document = _document(tmp_path, {"client_version": "0.153.1", "models": [{"slug": "m"}]})
    reading = model_discovery.read(document)
    assert reading.skew("0.153.1") == ()
    skew = reading.skew("0.149.0")
    assert skew and "different model sets" in skew[0]


def test_an_unrecorded_producer_is_skew_unknown_rather_than_agreement(tmp_path):
    document = _document(tmp_path, {"models": [{"slug": "m"}]})
    reading = model_discovery.read(document)
    assert reading.producer == UNKNOWN
    assert reading.skew("1.0.0") and "UNKNOWN" in reading.skew("1.0.0")[0]


# --- appearing and disappearing ----------------------------------------------


def test_a_disappearance_is_a_fact_about_a_document(tmp_path):
    before = model_discovery.read(_document(
        tmp_path, {"client_version": "1", "models": [{"slug": "a"}, {"slug": "b"}]}, "b.json"))
    after = model_discovery.read(_document(
        tmp_path, {"client_version": "2", "models": [{"slug": "b"}, {"slug": "c"}]}, "a.json"))
    changed = model_discovery.merge(after, before)
    assert changed["appeared"] == ("c",)
    assert changed["disappeared"] == ("a",)
    assert changed["unchanged"] == ("b",)
    assert "not a verdict about a model" in changed["note"]


def test_a_model_appearing_while_a_reading_is_already_held_is_a_diff_not_an_error(tmp_path):
    held = model_discovery.read(_document(tmp_path, {"models": [{"slug": "a"}]}, "held.json"))
    fresh = model_discovery.read(
        _document(tmp_path, {"models": [{"slug": "a"}, {"slug": "new"}]}, "fresh.json"))
    assert model_discovery.merge(fresh, held)["appeared"] == ("new",)


# --- refusals rather than silence --------------------------------------------


def test_an_entry_with_no_identifier_is_dropped_out_loud(tmp_path):
    document = _document(tmp_path, {"models": [{"slug": "a"}, {"description": "no name"}]})
    reading = model_discovery.read(document)
    assert reading.identifiers() == ("a",)
    assert any("dropped" in note for note in reading.notes)


def test_an_empty_catalogue_says_so_rather_than_reading_as_nothing_to_report(tmp_path):
    reading = model_discovery.read(_document(tmp_path, {"models": []}))
    assert reading.models == ()
    assert any("no readable model" in note for note in reading.notes)


def test_a_document_with_no_model_list_is_refused_rather_than_read_as_empty(tmp_path):
    with pytest.raises(DiscoveryError) as caught:
        model_discovery.read(_document(tmp_path, {"client_version": "1"}))
    assert "no list of models" in str(caught.value)


def test_an_unreadable_document_is_refused_with_its_cause(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(DiscoveryError) as caught:
        model_discovery.read(path)
    assert "not a readable discovery document" in str(caught.value)


def test_a_field_map_naming_something_nothing_reads_is_refused(tmp_path):
    with pytest.raises(DiscoveryError) as caught:
        model_discovery.read(_document(tmp_path, {"models": []}),
                             field_map={"colour": ("colour",)})
    assert "nothing reads" in str(caught.value)


def test_a_caller_supplied_field_map_reads_a_shape_this_pack_does_not_know(tmp_path):
    """The vendor shape is described by the caller, not known by Core."""
    document = _document(tmp_path, {
        "written_by": "7.7.7",
        "entries": [{"handle": "unusual-model", "window": 4096,
                     "rungs": [{"level": "brisk"}, {"level": "careful"}]}],
    })
    reading = model_discovery.read(document, field_map={
        "models": ("entries",), "identifier": ("handle",),
        "context_window": ("window",), "efforts": ("rungs",),
        "effort_name": ("level",), "producer": ("written_by",),
    })
    assert reading.identifiers() == ("unusual-model",)
    assert reading.producer == "7.7.7"
    model = reading.find("unusual-model")
    assert model.context_window == "4096"
    assert model.efforts == ("brisk", "careful")


def test_the_advertised_context_window_is_labelled_as_advertised(tmp_path):
    document = _document(tmp_path, {"models": [{"slug": "m", "context_window": 272000}]})
    model = model_discovery.read(document).find("m")
    assert model.context_window == "272000"
    assert "advertised context" in model.sentence()
