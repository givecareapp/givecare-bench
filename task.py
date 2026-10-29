"""One development family per run. Inspect owns generation and logs; no automatic scores."""

import hashlib
import json
import tomllib
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageUser, GenerateConfig
from inspect_ai.solver import Generate, Solver, TaskState, solver

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
PROJECT = ROOT / "pyproject.toml"
VERSION = tomllib.loads(PROJECT.read_text())["project"]["version"]


def case_path(family: str) -> Path:
    """The directory listing under cases/ is the family list."""
    path = CASES / str(family) / "case.json"
    if not isinstance(family, str) or Path(family).name != family or not path.is_file():
        known = sorted(p.parent.name for p in CASES.glob("*/case.json"))
        raise ValueError(f"Unknown family {family!r}; known families: {known}")
    return path


def load_case(family: str) -> dict:
    case = json.loads(case_path(family).read_text())
    if case["id"] != family:
        raise ValueError(f"Case id {case['id']!r} differs from directory {family!r}")
    return case


def opening(case: dict, variant: dict) -> str:
    """Fill the one placeholder with the variant's one varying fact."""
    [field] = set(variant) - {"id"}
    if case["opening"].count("{" + field + "}") != 1:
        raise ValueError(f"Opening must hold exactly one {{{field}}} placeholder")
    return case["opening"].replace("{" + field + "}", variant[field])


def samples(family: str = "backup_care") -> list[Sample]:
    case = load_case(family)
    return [
        Sample(
            id=f"{case['id']}/{variant['id']}",
            input=opening(case, variant),
            metadata={"followups": case["followups"]},
        )
        for variant in case["variants"]
    ]


@solver
def conversation() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Only deliver a continuation after the actual preceding model response.
        # Metadata is never inserted wholesale into the target's messages.
        state.metadata["completed_turns"] = 0
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
            # A reply is judgeable evidence only once complete. The log keeps truncated text.
            state.metadata["completed_turns"] = index + 1
        return state

    return solve


@task
def conversation_family(family: str = "backup_care") -> Task:
    return Task(
        dataset=samples(family),
        solver=conversation(),
        scorer=None,
        config=GenerateConfig(max_tokens=2048),
        metadata={
            "use": "development",
            "family": family,
            "benchmark_version": VERSION,
            "project_sha256": hashlib.sha256(PROJECT.read_bytes()).hexdigest(),
            "case_sha256": hashlib.sha256(case_path(family).read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "measurement": "unscored; review criteria are separate from generation",
        },
    )
