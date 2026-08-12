# Failure classification

Every lesson lands in exactly one layer. Getting this wrong is expensive in a
specific way: a domain-specific lesson written into generic governance degrades
every future project, and a generic failure hidden in a project skill has to be
learned again by the next one.

| Layer | It belongs here when |
|---|---|
| **Toolbelt bug** | A deterministic checker was wrong, missing, or unreachable from where the coordinator actually invokes it |
| **Core skill bug** | The semantic policy gave bad guidance, or gave none where it was needed |
| **Project skill bug** | Domain method was wrong — this project's, not every project's |
| **Project contract bug** | The scope, boundaries, dimensions or acceptance were wrong before work started |
| **Product bug** | The thing being built is defective; the process worked |
| **Environment / runtime failure** | Capacity, network, a provider, a machine. Nobody's competence |
| **Oracle defect** | The test was wrong, so the verdict was wrong in either direction |
| **Model capability** | A worker genuinely could not do this class of work |
| **Quota / capacity** | A provider stopped us. Environmental, and never evidence about a worker |
| **human-decision decision** | A human chose this, and the record should say so |
| **Accepted limitation** | Known, bounded, documented, and deliberately not fixed |

## The distinctions that get blurred

**Model capability against environment.** A worker that ran out of quota did not
fail at the work. A test runner that exited non-zero because it was broken says
nothing about the change. Both get attributed to the worker unless somebody
insists on the distinction, and the attribution narrows a standing that should
not move.

**Oracle defect against product bug.** They present identically: a failing test.
Ask what would be true if the test were right. If the answer is "nothing
observable is wrong with the product", the oracle is the defect.

**Toolbelt bug against core skill bug.** Could a rule have caught this
mechanically? Then a toolbelt checker should exist for it, and adding prose
instead is how a guarantee becomes a habit. Did it need judgement? Then no
checker would have helped, and adding one would have refused correct work.

**Project skill against core skill.** Would this lesson be true for a completely
different kind of project? If it needs the domain to be true, it is project
policy, however general it sounds while you are inside the domain.

## The rule that makes this worth doing

Update **only** the layer the lesson belongs to. A lesson from one project must
not silently become a universal rule, and a generic failure must not be filed
where only one project will ever read it.
