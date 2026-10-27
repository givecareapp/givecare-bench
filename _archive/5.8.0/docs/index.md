# Invisible Bench

Type: explanation.

<!-- benchmark:identity -->

**Invisible Bench evaluates caregiver-support conversations and produces a Jury
Card for each completed scan.** One judge path evaluates each active check:
yes/no questions answered as probabilities, and a code-owned rule that
derives the verdict. Safety and Care stay separate. There is no composite
score or model rank.

Read Ali Madad's paper,
[*InvisibleBench: A Deployment Gate for Caregiving Relationship AI*](https://arxiv.org/abs/2511.20733).
It describes the original benchmark. This site documents the current method.

A Jury Card is the report for one run. It lists each check's verdict counts and
quotes the failures. See [Method](methodology.md) for its contents. See the
[glossary](spec.md#glossary) for terms.

Each run keeps its `jury-card.md` and saved evidence in one private
`results/<run-id>/` directory. New runs get distinct UTC timestamps, including
runs of the same model. The saved plan, answers, and transcripts support
inspection and replay; judgments are derived from them.

The conversation includes both the caregiver and the care recipient's needs;
the [care dyad](coverage.md#care-dyad) checks cover them together.

- [Spec](spec.md): scope, parts, rubric, and glossary.
- [Run and inspect](quickstart.md): generate conversations, plan a scan, and read its Jury Card.
- [Method](methodology.md): understand the rules, rates, uncertainty, and limits.
- [Worked measurement](worked-example.md): inspect a public synthetic response, retained probabilities, and derived verdict.
- [Coverage](coverage.md): inspect development controls and scenario mappings.
- [Evaluator validation](validation.md): freeze independent expectations before measuring correctness.

Versions and counts come from the benchmark inventory. See
[benchmark/README.md](https://github.com/givecareapp/givecare-bench/blob/main/benchmark/README.md)
for the source files.

Historical releases keep their original bytes and version labels. They are
not results from the current method. The new method needs new judge runs.
