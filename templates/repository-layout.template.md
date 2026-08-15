# Repository-layout section — presentation convention

Pull this when a public README benefits from a layout section. It standardises
the **form**, never project-specific content.

## The rule

Render the layout as a compact filesystem tree using `├──`, `│` and `└──`, with
short project-facing descriptions beside the entries that earn one. **Derive it
from the tracked tree** (`git ls-files`), never by hand.

## Why a tree rather than an aligned list

An indented two-column list does not show nesting. A reader cannot tell which
directories are siblings, which are children, or where a package boundary falls
— all of which a tree shows for free. For a reviewed deliverable the layout
section is often the second thing a reviewer reads, and its job is to make the
architecture scannable in seconds.

The stronger argument is checkability. On one project the layout section had
survived four review rounds untouched — reviews concentrate on claims and
numbers, so presentation defects persist. Deriving the tree from `git ls-files`
immediately exposed that the hand-maintained list had dropped **six real
modules**. The drift was invisible in list form and obvious in tree form,
because a tree built from the tracked tree can be verified and a hand-aligned
list cannot.

## Shape

```
src/
├── package_name/
│   ├── ingest.py          one-line purpose
│   ├── analysis.py        one-line purpose
│   └── report.py          one-line purpose
├── tests/                 NN tests; see the validation section
└── outputs/               generated, not committed — rebuilt by `<command>`
```

## Constraints

- **Do not force a layout section** where it adds nothing — a small
  single-purpose repository does not need one.
- **Reviewer-relevant structure only.** Do not expand to completeness. Summarise
  repetitive contents; name generated and vendored directories in one line.
- **Never restructure a real repository to make its tree prettier.**
- **Verify every path shown against the tracked tree before publishing.** The
  point of the convention is that this check is possible; skipping it discards
  the whole benefit.
