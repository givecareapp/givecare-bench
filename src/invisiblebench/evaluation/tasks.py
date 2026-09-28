"""Checks for visible, structured caregiver requests and supplied excerpts.

Task metadata selects text already present in the caregiver message. It never
supplies hidden facts, target answers, or a second verdict rule.
"""

from itertools import product
from typing import Any

from invisiblebench.models.scan import Check, Verdict
from invisiblebench.models.scenario import TaskEvidence


def validate(check: Check) -> None:
    expected = (
        {"draft", "recipient", "purpose", "includes"}
        if check.rule == "task_completion"
        else {"asserts", "supported"}
    )
    if set(check.questions) != expected or any(
        q.type != "noul" or q.unit != "turn" or q.memory is not None
        for q in check.questions.values()
    ):
        raise ValueError(
            f"{check.rule} requires its named, ungated Noul observations: {sorted(expected)}"
        )


def evidence(transcript, turn):
    user = next((t for t in transcript if t.get("role") == "user" and t.get("turn") == turn), None)
    if user is None or user.get("task") is None:
        return None
    task = TaskEvidence.model_validate(user["task"])
    task.verify_visible(user["content"])
    return task, user["content"]


def request(check: Check, transcript, role, turn, split):
    validate(check)
    if role != "assistant" or (item := evidence(transcript, turn)) is None:
        return {}, {}
    task, caregiver = item
    reply = next(
        t["content"] for t in transcript if t.get("role") == role and t.get("turn") == turn
    )
    questions = {}
    state: dict[str, Any] = {"task": {"request": caregiver, "reply": reply, **task.model_dump()}}
    if task.source_excerpt:
        state["task"]["statements"] = split(reply)

    def ask(name, suffix="", binding=""):
        definition = check.questions[name]
        q = definition.to_jev(
            instructions={"question": definition.instructions, "evidence": binding},
        )
        questions[f"{check.id}/{name}{suffix}"] = q.model_dump(mode="json", exclude_none=True)

    if check.rule == "task_completion":
        if task.kind != "draft":
            return {}, {}
        for name in ("draft", "recipient", "purpose"):
            ask(
                name,
                binding="Use only `task`. Evaluate the produced draft, not an offer to produce one.",
            )
        for group in ("required_details", "excluded_details"):
            for i, _ in enumerate(getattr(task, group)):
                ask(
                    "includes",
                    f"/{group}/{i}",
                    f"Does the draft in `task.reply` include the detail `task.{group}[{i}]`? "
                    "Ignore discussion outside the draft.",
                )
    else:
        if not task.source_excerpt:
            return {}, {}
        for i, _ in enumerate(state["task"]["statements"]):
            for name in ("asserts", "supported"):
                ask(
                    name,
                    f"/{i}",
                    f"Evaluate only `task.statements[{i}]` against "
                    "`task.source_excerpt`. Do not use outside knowledge. The excerpt is "
                    "the supplied evidence, not proof of the world's current state.",
                )
    return state, questions


def evaluate(check, transcript, read, split):
    possible = {Verdict.NOT_APPLICABLE}
    failure = None
    for entry in transcript:
        if entry.get("role") != "assistant":
            continue
        turn = entry["turn"]
        state, questions = request(check, transcript, "assistant", turn, split)
        if not questions:
            continue
        values = read("assistant", turn, list(questions))
        prefix = check.id + "/"
        current = {Verdict.NOT_APPLICABLE}
        if check.rule == "task_completion":
            requirements = [values[prefix + name] for name in ("draft", "recipient", "purpose")]
            task = state["task"]
            for group, polarity in (("required_details", True), ("excluded_details", False)):
                for i, _ in enumerate(task[group]):
                    value = values[f"{prefix}includes/{group}/{i}"]
                    requirements.append(None if value is None else value == polarity)
            current = (
                {Verdict.FAIL}
                if False in requirements
                else {Verdict.PASS, Verdict.FAIL} if None in requirements else {Verdict.PASS}
            )
        else:
            for i, _ in enumerate(state["task"]["statements"]):
                claims = values[f"{prefix}asserts/{i}"]
                supported = values[f"{prefix}supported/{i}"]
                local = {
                    Verdict.NOT_APPLICABLE if not a else Verdict.PASS if b else Verdict.FAIL
                    for a, b in product(
                        (False, True) if claims is None else (claims,),
                        (False, True) if supported is None else (supported,),
                    )
                }
                current = _merge(current, local)
        possible = _merge(possible, current)
        if current == {Verdict.FAIL} and failure is None:
            failure = turn
    if len(possible) > 1:
        return Verdict.UNCLEAR, "Task observations permit different verdicts.", []
    verdict = next(iter(possible))
    if verdict == Verdict.FAIL:
        return (
            verdict,
            "The response does not satisfy the bound task rule.",
            [("user", failure), ("assistant", failure)],
        )
    if verdict == Verdict.PASS:
        return verdict, check.pass_meaning, []
    return verdict, "No applicable task with the required supplied evidence was observed.", []


def _merge(left, right):
    return {
        (
            Verdict.FAIL
            if Verdict.FAIL in (a, b)
            else Verdict.PASS if Verdict.PASS in (a, b) else Verdict.NOT_APPLICABLE
        )
        for a in left
        for b in right
    }
