from __future__ import annotations

import importlib.util
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

from .models import CandidateStep


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = PROJECT_ROOT / "skills"
SKILL_ENV_VAR = "OPENCLAW_PLANNER_SKILL"
EXECUTION_TOOLS = {
    "file_writer",
    "command_runner",
    "deploy_runner",
    "mobile_gui_runner",
    "mobile_cli_runner",
    "mcp_tool_runner",
}


@dataclass(slots=True)
class PlannerSkillResult:
    enabled: bool
    skill_name: str = ""
    decision: dict[str, Any] | None = None
    error: str = ""


def route_with_planner_skill(goal: str, permission_mode: str) -> PlannerSkillResult:
    skill_name = os.environ.get(SKILL_ENV_VAR, "").strip()
    if not skill_name or skill_name.lower() in {"off", "none", "disabled"}:
        return PlannerSkillResult(enabled=False)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", skill_name):
        return PlannerSkillResult(enabled=True, skill_name=skill_name, error="invalid skill slug")
    try:
        module = _load_skill_module(skill_name)
        decision = module.route_task(goal, permission_mode=permission_mode)
        errors = module.validate_decision(decision)
        if errors:
            return PlannerSkillResult(
                enabled=True,
                skill_name=skill_name,
                error=f"invalid route decision: {'; '.join(errors)}",
            )
        return PlannerSkillResult(enabled=True, skill_name=skill_name, decision=decision)
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        return PlannerSkillResult(enabled=True, skill_name=skill_name, error=f"{type(exc).__name__}: {exc}")


def apply_planner_skill_route(
    candidates: Iterable[CandidateStep],
    decision: dict[str, Any],
) -> tuple[list[CandidateStep], list[str]]:
    target_tools = planner_skill_target_tools(decision)
    best_by_tool: dict[str, CandidateStep] = {}
    for candidate in candidates:
        current = best_by_tool.get(candidate.tool_name)
        if current is None or candidate.score > current.score:
            best_by_tool[candidate.tool_name] = candidate
    selected = [best_by_tool[tool] for tool in target_tools if tool in best_by_tool]
    return selected, target_tools


def planner_skill_target_tools(decision: dict[str, Any]) -> list[str]:
    execution_tools = [
        tool
        for tool in decision.get("execution_tools", [])
        if tool in EXECUTION_TOOLS
    ][:2]
    if not execution_tools:
        return ["goal_analyzer", "planner", "risk_model", "verifier"]

    target = ["risk_model", "planner", *execution_tools, "verifier"]
    if decision.get("safety_guard"):
        if len(target) < 5:
            target.insert(1, "safety_guard")
        else:
            target = ["risk_model", "safety_guard", *execution_tools, "verifier"]
    return target[:5]


@lru_cache(maxsize=4)
def _load_skill_module(skill_name: str) -> ModuleType:
    skills_root = SKILLS_ROOT.resolve()
    skill_root = (skills_root / skill_name).resolve()
    if not skill_root.is_relative_to(skills_root):
        raise ValueError("skill path escapes workspace skills root")
    if not (skill_root / "SKILL.md").is_file():
        raise FileNotFoundError(f"missing SKILL.md for {skill_name}")
    script_path = skill_root / "scripts" / "route_task.py"
    if not script_path.is_file():
        raise FileNotFoundError(f"missing route_task.py for {skill_name}")
    spec = importlib.util.spec_from_file_location(f"openclaw_skill_{skill_name.replace('-', '_')}", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load planner skill {skill_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
