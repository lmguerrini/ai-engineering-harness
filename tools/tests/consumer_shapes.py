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
UNKNOWN_BLOCKS = """
dimensions:
  correctness: "the thing does what was asked"
  clarity: "a reader can follow it"
critical_domains:
  - "input handling"
mutation_policy:
  scope: "only the declared repository"
approval:
  integration: "coordinator"
validation_profiles:
  focused:
    command: "python3 -m pytest -q"
    when: "every task gate"
hitl_selections:
  release: "human"
private_terms:
  project_terms: ["ProjectCodename"]
  project_patterns: ["\\bProject-?Codename\\b"]
  identity_only_terms: []
workspace_classification:
  generated: ["build/*", "dist/*"]
  content_exempt: [".gitignore", "docs/figures/*.png"]
publication:
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
SHAPES: dict[str, tuple[str, str]] = {
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
    if shape not in SHAPES:
        raise KeyError(f"no consumer shape named {shape!r}; known: {', '.join(sorted(SHAPES))}")
    _description, template = SHAPES[shape]
    return template.format(**values)
