"""One development family. Inspect owns generation and logs; no automatic scores."""

import hashlib
import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageUser, GenerateConfig
from inspect_ai.solver import Generate, Solver, TaskState, solver

ROOT = Path(__file__).resolve().parent
CASE = ROOT / "cases" / "backup_care" / "case.json"


def samples() -> list[Sample]:
    family = json.loads(CASE.read_text())
    return [
        Sample(
            id=f"{family['id']}/{variant['id']}",
            input=family["opening"].replace("{availability}", variant["availability"]),
            metadata={"followups": family["followups"]},
        )
        for variant in family["variants"]
    ]


@solver
def conversation() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Only deliver a continuation after the actual preceding model response.
        # Metadata is never inserted wholesale into the target's messages.
        for index in range(len(state.metadata["followups"]) + 1):
            if state.completed:
                break
            if index:
                state.messages.append(
                    ChatMessageUser(content=state.metadata["followups"][index - 1])
                )
            state = await generate(state)
            if state.output.stop_reason in {"max_tokens", "model_length"}:
                raise RuntimeError(f"Incomplete response at user turn {index + 1}")
        return state

    return solve


@task
def backup_care() -> Task:
    return Task(
        dataset=samples(),
        solver=conversation(),
        scorer=None,
        config=GenerateConfig(max_tokens=2048),
        metadata={
            "use": "development",
            "case_sha256": hashlib.sha256(CASE.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "measurement": "unscored; review criteria are separate from generation",
        },
    )
