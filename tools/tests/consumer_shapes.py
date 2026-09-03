"""Representative consumer contract shapes, derived from real ones, public-safe.

**Why this file exists.** Four repository-only audit rounds passed while the
contract reader refused a real project's contract outright. The release was
green against its own fixtures and broken against the only real consumer that
had a Project Context. Repository self-tests are not consumer compatibility, and
nothing in the suite said so.

**What it is not.** No content from any real project is here. Every path is a
placeholder resolved against a temporary directory at test time, so the suite
does not depend on any particular machine, any particular person's home, or the
continued existence of any private project. A shape is a *shape*: the structure
that made a real consumer behave the way it did, with the substance removed.

Each shape names the compatibility class it preserves. Adding a class here is
how a future release inherits the lesson; deleting one silently is how it loses
it, which is why the test module asserts the class list rather than iterating
whatever happens to be present.
"""

from __future__ import annotations

#: Blocks every real consumer contract carries that Core never reads. Core must
#: load a contract that declares things it knows nothing about — all three real
#: consumers do, and a reader that refused unknown blocks would have broken
#: every one of them.
#: The blocks a real consumer carries that Core never reads, minus the two it
#: DOES read — profiles and publication — so a shape that declares its own can
#: still carry the unknown-block property. Split out rather than duplicated:
#: `UNKNOWN_BLOCKS` below is byte-identical to what it always was.
_UNKNOWN_BLOCKS_CORE = """
dimensions:
  correctness: "the thing does what was asked"
  clarity: "a reader can follow it"
critical_domains:
  - "input handling"
mutation_policy:
  scope: "only the declared repository"
approval:
  integration: "coordinator"
"""

_UNKNOWN_BLOCKS_TAIL = """hitl_selections:
  release: "human"
private_terms:
  project_terms: ["ProjectCodename"]
  project_patterns: ["\\bProject-?Codename\\b"]
  identity_only_terms: []
workspace_classification:
  generated: ["build/*", "dist/*"]
  content_exempt: [".gitignore", "docs/figures/*.png"]
"""

UNKNOWN_BLOCKS = _UNKNOWN_BLOCKS_CORE + """validation_profiles:
  focused:
    command: "python3 -m pytest -q"
    when: "every task gate"
""" + _UNKNOWN_BLOCKS_TAIL + """publication:
  release_ref: "main"
  publishable: ["src/**", "README.md"]
"""

#: The minimum every shape needs to be a project at all.
_HEADER = """project:
  name: "{name}"
  repo_path: "{repo}"
  integration_ref: "integration"
  release_ref: "main"

capabilities:
  - id: "C1-first"
    goal: "The first capability"
    depends_on: []
"""

_LEGACY_PIN = """
pack:
  version_adopted: "{version}"
  adoption_boundary: "a newer pack version is adopted only at a capability boundary"
"""

_FULL_PIN = """
pack:
  root_path: "{root}"
  version_adopted: "{version}"
  sha_adopted: "{sha}"
  tree_digest_sha256: "{digest}"
  state_adopted: "{state}"
  adoption_boundary: "a newer pack version is adopted only at a capability boundary"
"""

_CONTEXT_FULL = """
project_context:
  context_id: "PROJECT-CONTEXT-001"
  reference_path: "{context}"
  control_revision: 12
  digest: "{context_digest}"
  authority_role: "DURABLE_SEMANTIC_PRODUCT_AUTHORITY"
  activated: true
"""

#: The shape that broke the release: identity fields present except the digest,
#: which the real project keeps in prose rather than in a field.
_CONTEXT_NO_DIGEST = """
project_context:
  context_id: "PROJECT-CONTEXT-001"
  reference_path: "{context}"
  control_revision: 12
  authority_role: "DURABLE_SEMANTIC_PRODUCT_AUTHORITY"
  activated: true
"""

_REQUIRES_CONTEXT = """
requires:
  project_context: true
"""


#: name -> (compatibility class, template). The class string is what a reader
#: should understand this shape to be protecting.
#: Everything RP2.3 adds, all of it optional. The MINOR claim rests on the
#: absence of these keys being indistinguishable from the previous release.
_PUBLICATION_INTENT = """
publication:
  intent: "{intent}"
"""

_REPRODUCIBLE_PROFILES = """
validation_profiles:
  focused:
    command: "python3 -m pytest -q"
    reproducible_by: developer_machine
  full:
    command: "python3 -m pytest"
    reproducible_by: public_clone
"""

_CLOSURE_POLICY = """
closure:
  refuses_on_unrun: false
"""

_ADAPTER_WITH_EXECUTABLE = """
adapters:
  - id: "a-worker"
    locator: "{adapter}"
    digest: "{adapter_digest}"
    executable: "echo"
    version_command: "echo 1.2.3"
    qualified_version: "1.2.3"
"""

#: The pre-2.1 shape, still carried by a real project on the machine this
#: release was built on. It must NOT load — it is in its own collection for
#: that reason, and what is asserted about it is the message.
_LEGACY_FLAT_TERMS = """project:
  name: "{name}"
  repo_path: "{repo}"
private_terms:
  - 'session id'
  - 'worker id'
"""

#: Shapes that must be REFUSED, and what the refusal has to say. A shape that
#: cannot load has no other behaviour to test, so it cannot sit in `SHAPES`
#: beside shapes whose whole point is that they load.
REFUSED_SHAPES: dict[str, tuple[str, str, str]] = {
    "legacy_flat_private_terms": (
        "the pre-2.1 list form of `private_terms`, still live on a real machine and unreadable "
        "by every tool since the schema changed; the refusal must name the migration rather "
        "than report a type, because a project told its file is malformed does not learn that "
        "it is a generation behind",
        _LEGACY_FLAT_TERMS,
        "pre-2.1 schema",
    ),
}

SHAPES: dict[str, tuple[str, str]] = {
    "unchanged_since_2_2": (
        "a contract carrying none of the keys this release adds; the MINOR claim is that it "
        "loads and behaves exactly as it did, so every new key must be optional",
        _HEADER + _FULL_PIN + UNKNOWN_BLOCKS,
    ),
    "adapter_with_executable": (
        "an adapter declaring the program it drives, so the pin covers the executable and not "
        "only the definition files whose digest it already carried",
        _HEADER + _FULL_PIN + UNKNOWN_BLOCKS + _ADAPTER_WITH_EXECUTABLE,
    ),
    "internal_intent": (
        "a project that declares itself internal and declines to close over an unrun profile; "
        "it must not be walked through publication ceremony and must keep every safety invariant",
        _HEADER + _FULL_PIN + _UNKNOWN_BLOCKS_CORE + _UNKNOWN_BLOCKS_TAIL
        + _PUBLICATION_INTENT + _REPRODUCIBLE_PROFILES + _CLOSURE_POLICY,
    ),
    "public_intent": (
        "a project that declares it intends to publish and names the environment each profile "
        "is reproducible by; it carries both halves of the obligation set",
        _HEADER + _FULL_PIN + _UNKNOWN_BLOCKS_CORE + _UNKNOWN_BLOCKS_TAIL
        + _PUBLICATION_INTENT + _REPRODUCIBLE_PROFILES,
    ),
    "legacy_pin_version_only": (
        "a pin from before the four-field identity: version and nothing else. Two of "
        "three real consumers are in this state. It must classify as LEGACY and say so, "
        "never as verified and never as a defect in the project",
        _HEADER + _LEGACY_PIN + UNKNOWN_BLOCKS,
    ),
    "full_pin_qualified_no_context": (
        "the fully identified pin against a qualified release, with no Project Context. "
        "The ordinary healthy shape for a fixture or utility: READY",
        _HEADER + _FULL_PIN + UNKNOWN_BLOCKS,
    ),
    "full_pin_context_verified": (
        "a fully identified pin and a Project Context whose declared digest matches the "
        "tree. The healthy shape for a semantic product: READY",
        _HEADER + _FULL_PIN + _CONTEXT_FULL + UNKNOWN_BLOCKS,
    ),
    "context_declared_without_digest": (
        "the real shape that made `ProjectContract.load` raise, so the contract could "
        "not be read by any tool for any purpose. It must load, and the context must "
        "report UNVERIFIABLE naming the missing field",
        _HEADER + _FULL_PIN + _CONTEXT_NO_DIGEST + UNKNOWN_BLOCKS,
    ),
    "context_required_and_absent": (
        "a project that declares it requires durable semantic authority and declares "
        "none. The class that could not be expressed at all before 2.2.0: absence had "
        "to read as clean, for every project, including products whose correctness "
        "depends on it",
        _HEADER + _FULL_PIN + _REQUIRES_CONTEXT + UNKNOWN_BLOCKS,
    ),
    "context_required_and_verified": (
        "the same declaration, satisfied. Proves the requirement is a real condition "
        "and not an unconditional refusal",
        _HEADER + _FULL_PIN + _REQUIRES_CONTEXT + _CONTEXT_FULL + UNKNOWN_BLOCKS,
    ),
    "full_pin_that_does_not_verify": (
        "a pin with every field present, pointing at a root that holds a DIFFERENT release. "
        "The state a real consumer is in whenever somebody checks a branch out in the "
        "directory it pinned, and the one path in the readiness checker that no test "
        "constrained: a mutation making the pin always verify survived the whole suite green",
        _HEADER + _FULL_PIN + UNKNOWN_BLOCKS,
    ),
    "pin_to_an_unqualified_release": (
        "a pin that verifies perfectly against a root in state IN_PROGRESS. The root IS "
        "what was pinned, and what was pinned is not adoptable — two questions, and only "
        "the first had an answer before this release",
        _HEADER + _FULL_PIN + UNKNOWN_BLOCKS,
    ),
}


def render(shape: str, **values: object) -> str:
    """One shape, with its placeholders resolved against a caller's paths."""
    if shape in SHAPES:
        return SHAPES[shape][1].format(**values)
    if shape in REFUSED_SHAPES:
        return REFUSED_SHAPES[shape][1].format(**values)
    raise KeyError(
        f"no consumer shape named {shape!r}; known: "
        f"{', '.join(sorted(set(SHAPES) | set(REFUSED_SHAPES)))}"
    )
