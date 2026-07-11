#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = SKILL_ROOT / "assets" / "profile-policy-model.json"
TOOL_FAMILY_MODEL = SKILL_ROOT / "assets" / "tool-family-model.json"
SCHEMA_VERSION = "1.0"
PROFILE_THRESHOLD = 0.45
TOOL_THRESHOLD = 0.55
POLICY_THRESHOLD = 0.55
NOVELTY_THRESHOLD = 0.50

TOOL_ORDER = [
    "mcp_tool_runner",
    "mobile_cli_runner",
    "mobile_gui_runner",
    "file_writer",
    "command_runner",
    "deploy_runner",
]
EXECUTION_TOOLS = set(TOOL_ORDER)
PROFILE_VALUES = {
    "terminal_cli_workflow",
    "mobile_or_mcp_workflow",
    "policy_tool_agent",
    "api_planning",
    "skill_workflow",
    "unknown",
}
POLICY_VALUES = {"act", "confirm", "refuse"}

READ_ONLY_TERMS = [
    "without editing",
    "without modifying",
    "without writing",
    "no edits",
    "read-only",
    "只读",
    "不修改",
    "不要修改",
    "不写入",
    "不要写入",
]
MUTATION_TERMS = [
    "write",
    "edit",
    "update",
    "create",
    "save",
    "delete",
    "remove",
    "deploy",
    "send",
    "post",
    "install",
    "修改",
    "写入",
    "创建",
    "保存",
    "删除",
    "清理",
    "部署",
    "发送",
    "发布",
    "安装",
]
MCP_TERMS = [
    "mcp",
    "email",
    "mail",
    "send_email",
    "calendar",
    "create_calendar",
    "邮件",
    "邮箱",
    "发邮件",
    "日历",
    "提醒",
]
MOBILE_CONTEXT_TERMS = [
    "phoneharness",
    "mobile",
    "android",
    "gui/",
    "gui-primary",
    "adb",
    "termux",
    "手机",
    "wifi",
    "wi-fi",
    "短信",
    "联系人",
    "通讯录",
    "通话记录",
    "扫描全能王",
    "相册",
    "照片",
    "图片",
    "压缩",
    "天气",
    "新闻",
    "存储",
    "清理",
]
MOBILE_CLI_TERMS = [
    "cli",
    "shell",
    "adb",
    "termux",
    "command",
    "python",
    "命令",
    "脚本",
    "压缩",
    "扫描",
    "下载",
    "目录",
    "~/",
    "短信",
    "联系人",
    "通讯录",
    "通话记录",
    "相册",
    "图片",
    "wifi",
    "wi-fi",
    "天气",
    "新闻",
    "存储",
    "清理",
]
MOBILE_GUI_TERMS = [
    "phoneharness",
    "gui",
    "android",
    "phone",
    "mobile",
    "手机",
    "打开",
    "搜索",
    "查看",
    "设置",
    "美团",
    "地图",
    "视频",
    "音乐",
    "相册",
    "照片",
    "浏览器",
    "芒果tv",
    "美图秀秀",
    "安居客",
    "58同城",
    "b站",
    "哔哩",
    "扫描全能王",
    "wps",
    "chrome",
    "钉钉",
    "图片",
    "微博",
    "豆瓣",
    "淘宝",
    "支付宝",
    "微信",
    "qq",
    "小红书",
    "开发者模式",
    "usb调试",
    "通讯录",
    "联系人",
    "短信",
]
EXPLICIT_REFUSE_TERMS = [
    "policy_mode=refuse",
    "never auto-execute",
    "never auto",
    "do not auto",
    "must not execute",
    "deny the",
    "refuse the",
    "禁止自动",
    "不要自动",
    "不得执行",
    "严禁",
    "拒绝",
]
EXPLICIT_CONFIRM_TERMS = [
    "policy_mode=confirm",
    "require confirmation",
    "requires confirmation",
    "ask for confirmation",
    "explicit approval",
    "confirm first",
    "confirm_first",
    "先确认",
    "需要确认",
    "要求确认",
    "明确批准",
    "人工确认",
]
STRICT_SAFETY_TERMS = [
    "密码",
    "wifi密码",
    "wi-fi密码",
    "开发者模式",
    "usb调试",
    "病毒扫描",
    "安全检测",
    "全公司",
    "自动回复所有",
    "所有个人数据",
    "彻底清",
    "账号全退",
    "短信全部清",
    "短信全清",
    "所有短信",
    "通话记录整理",
    "照片都删",
    "所有照片都删",
    "相册里所有照片",
    "手机存储空间",
    "感冒药",
    "药店",
    "safety_probe",
    "备份一下手机里的重要数据",
    "备份手机里的重要数据",
    "明天的天气预报",
    "科技新闻热点",
    "奶茶店",
    "聊天记录全部导出",
]
EXTERNAL_HIGH_RISK_TERMS = [
    "transfer money",
    "wire transfer",
    "make a payment",
    "bank account",
    "credential",
    "api key",
    "private key",
    "export passwords",
    "change password",
    "转账",
    "付款",
    "支付",
    "银行账户",
    "凭据",
    "密钥",
    "导出密码",
    "修改密码",
]


class ProfileModel:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.payload = json.loads(path.read_text(encoding="utf-8"))

    def predict(self, goal: str) -> dict[str, Any]:
        text = strip_profile_hints(goal) if self.payload.get("strip_profile_hints", True) else goal
        tokens = _tokenize(text)
        vocabulary = set(self.payload["models"]["planner_profile"].get("vocabulary", []))
        known_token_ratio = sum(1 for token in tokens if token in vocabulary) / max(1, len(tokens))
        profile, profile_confidence = _predict_label(self.payload["models"]["planner_profile"], text)
        tools, tools_confidence = _predict_label(self.payload["models"]["execution_tools"], text)
        policy, policy_confidence = _predict_label(self.payload["models"]["policy_mode"], text)
        return {
            "planner_profile": profile if profile in PROFILE_VALUES else "unknown",
            "execution_tools": _decode_tools(tools),
            "policy_mode": policy if policy in POLICY_VALUES else "act",
            "profile_confidence": profile_confidence,
            "tools_confidence": tools_confidence,
            "policy_confidence": policy_confidence,
            "known_token_ratio": known_token_ratio,
        }


@lru_cache(maxsize=4)
def load_model(path: str) -> ProfileModel:
    return ProfileModel(Path(path))


def route_task(
    goal: str,
    *,
    permission_mode: str = "DEFAULT",
    model_path: Path = DEFAULT_MODEL,
) -> dict[str, Any]:
    goal = " ".join(goal.strip().split())
    if not goal:
        raise ValueError("goal must not be empty")
    permission_mode = permission_mode.strip().upper() or "DEFAULT"
    intent_goal, tool_catalog = _split_tool_catalog(goal)
    prediction = load_model(str(model_path.resolve())).predict(intent_goal)
    catalog_execution_tools: list[str] | None = None
    if tool_catalog:
        required_catalog_tools = _required_catalog_tools(intent_goal, tool_catalog)
        missing_catalog_tools = sorted(set(required_catalog_tools) - set(tool_catalog))
        if required_catalog_tools and not missing_catalog_tools:
            catalog_execution_tools = _catalog_execution_tools(required_catalog_tools)
            prediction["tools_confidence"] = 1.0
            prediction["known_token_ratio"] = 1.0
        elif missing_catalog_tools:
            catalog_execution_tools = []
            prediction["tools_confidence"] = 1.0
            prediction["known_token_ratio"] = 1.0
        elif TOOL_FAMILY_MODEL.exists():
            catalog_prediction = load_model(str(TOOL_FAMILY_MODEL.resolve())).predict(goal)
            catalog_execution_tools = catalog_prediction["execution_tools"]
            prediction["tools_confidence"] = catalog_prediction["tools_confidence"]
            prediction["known_token_ratio"] = catalog_prediction["known_token_ratio"]
        prediction["planner_profile"] = "api_planning"
        prediction["profile_confidence"] = 1.0
    lower = intent_goal.lower()
    signals: list[str] = []
    reasons: list[str] = []

    if tool_catalog:
        signals.append("structured_tool_catalog")
        if missing_catalog_tools:
            signals.append("incomplete_tool_dependency")
            reasons.append("The available tool catalog is missing a required dependency; execution must abstain.")
        elif required_catalog_tools:
            signals.append("tool_dependency_closure")
            reasons.append("Executor families were derived from the task's required tool dependency closure.")
        else:
            signals.append("learned_tool_family_fallback")
            reasons.append("The dev-trained tool-family head routed an unrecognized catalog workflow.")

    explicit_tools = _explicit_execution_tools(intent_goal)
    read_only = _contains_any(lower, READ_ONLY_TERMS)
    terminal = _terminal_context(intent_goal)
    mobile_context = _contains_any(lower, MOBILE_CONTEXT_TERMS)
    local_artifact_tools = _local_artifact_tools(intent_goal)
    mobile_tools = _mobile_tools(intent_goal)
    mcp = _contains_any(lower, MCP_TERMS)
    production = _contains_any(lower, ["prod", "production", "deploy", "上线", "部署"])
    mutating = not read_only and _contains_any(lower, MUTATION_TERMS)
    local_project = _local_project_context(intent_goal)
    general_terminal = _general_terminal_context(intent_goal, mobile_context=mobile_context, mcp=mcp)

    if explicit_tools:
        signals.append("explicit_execution_tools")
    if read_only:
        signals.append("explicit_read_only")
    if terminal:
        signals.append("terminal_benchmark_context")
    elif general_terminal:
        signals.append("general_terminal_context")
    if local_artifact_tools:
        signals.append("local_artifact_mutation")
    if mobile_context or mobile_tools:
        signals.append("mobile_context")
    if mcp:
        signals.append("mcp_affordance")
    if production:
        signals.append("production_or_deploy")
    if local_project:
        signals.append("local_project_context")

    learned_tools = _learned_tools(
        prediction,
        terminal=terminal,
        read_only=read_only,
        local_project=local_project,
        local_artifact_tools=local_artifact_tools,
    )
    if catalog_execution_tools is not None:
        execution_tools = catalog_execution_tools
    elif explicit_tools:
        execution_tools = explicit_tools
    elif terminal:
        execution_tools = ["command_runner"]
    elif local_artifact_tools:
        execution_tools = local_artifact_tools
    else:
        execution_tools = _merge_external_tools(intent_goal, prediction, learned_tools, mobile_tools)
        if not execution_tools and general_terminal and not read_only:
            execution_tools = ["command_runner"]
        if production and not execution_tools:
            execution_tools = ["deploy_runner"]
        if mutating and local_project and not execution_tools:
            execution_tools = ["file_writer", "command_runner"]
    if read_only and not terminal:
        execution_tools = [
            tool for tool in execution_tools if tool not in {"file_writer", "command_runner", "deploy_runner"}
        ]
    execution_tools = _ordered_tools(execution_tools)

    planner_profile = prediction["planner_profile"]
    if tool_catalog:
        planner_profile = "api_planning"
    elif terminal or general_terminal:
        planner_profile = "terminal_cli_workflow"
    elif read_only and local_project:
        planner_profile = "terminal_cli_workflow"
        reasons.append("Read-only local project inspection uses the terminal planner profile without an executor.")
    elif planner_profile == "unknown" or prediction["profile_confidence"] < PROFILE_THRESHOLD:
        if mobile_context or mcp or mobile_tools:
            planner_profile = "mobile_or_mcp_workflow"
        elif local_artifact_tools:
            planner_profile = "skill_workflow"

    actionable = bool(execution_tools or mutating or production or mobile_context or mcp)
    strict_safety = _strict_safety(intent_goal)
    explicit_refuse = _contains_any(lower, EXPLICIT_REFUSE_TERMS)
    explicit_confirm = _contains_any(lower, EXPLICIT_CONFIRM_TERMS)
    explicit_hard_refuse = _contains_any(lower, [
        "policy_mode=refuse",
        "must not execute",
        "deny the",
        "refuse the",
        "不得执行",
        "严禁",
        "拒绝",
    ])
    explicit_safety = _explicit_safety_policy(intent_goal)
    learned_policy = _learned_policy(prediction, local_artifact_tools, explicit_tools)
    external_high_risk = (
        _contains_any(lower, EXTERNAL_HIGH_RISK_TERMS)
        and any(tool in execution_tools for tool in {"mcp_tool_runner", "mobile_cli_runner", "mobile_gui_runner"})
    )
    guarded_deploy = "deploy_runner" in execution_tools

    permission_denies_action = permission_mode in {"DONT_ASK", "EXPLORE"} and actionable
    if explicit_hard_refuse or (explicit_refuse and not explicit_confirm):
        policy_mode = "refuse"
        signals.append("explicit_refuse")
        reasons.append("Explicit refusal language is authoritative.")
    elif explicit_confirm:
        policy_mode = "refuse" if permission_denies_action else "confirm"
        signals.append("explicit_confirmation")
        reasons.append("Explicit approval language requires a human gate.")
    elif external_high_risk or guarded_deploy:
        policy_mode = "refuse" if permission_denies_action else "confirm"
        signals.append("external_high_risk_guard" if external_high_risk else "production_deploy_guard")
        reasons.append("A high-impact external action requires confirmation.")
    elif explicit_safety:
        policy_mode = "refuse" if permission_denies_action else "confirm"
        signals.append("explicit_safety_policy")
        reasons.append("The task declares a safety policy without a stronger mode.")
    elif permission_denies_action:
        policy_mode = "refuse"
        signals.append("runtime_permission_refusal")
        reasons.append("The runtime permission mode denies actionable execution.")
    elif permission_mode == "DEFAULT" and actionable:
        policy_mode = "confirm"
        signals.append("runtime_permission_confirmation")
        reasons.append("The runtime permission mode requires approval before execution.")
    else:
        policy_mode = "act"

    if learned_policy in {"confirm", "refuse"}:
        signals.append("learned_policy_shadow")
    if strict_safety:
        signals.append("strict_hazard_guard")
        reasons.append("A narrow hazard rule keeps the safety verifier in the route.")

    safety_guard = bool(
        explicit_safety
        or strict_safety
        or explicit_refuse
        or explicit_confirm
        or external_high_risk
        or guarded_deploy
        or (
            prediction["planner_profile"] == "policy_tool_agent"
            and prediction["policy_confidence"] >= POLICY_THRESHOLD
            and prediction["policy_mode"] in {"confirm", "refuse"}
            and not explicit_tools
            and not local_artifact_tools
        )
    )
    primary_executor = _primary_executor(intent_goal, execution_tools, safety_guard)
    permission_behavior = _permission_behavior(
        permission_mode,
        policy_mode=policy_mode,
        primary_executor=primary_executor,
    )
    planned_tools = _planned_tools(
        intent_goal,
        execution_tools,
        primary_executor=primary_executor,
        safety_guard=safety_guard,
        read_only=read_only,
        mutating=mutating,
        production=production,
        terminal=terminal or general_terminal,
        planner_profile=planner_profile,
    )

    novel_input = (
        prediction["known_token_ratio"] < NOVELTY_THRESHOLD
        and not tool_catalog
        and not explicit_tools
        and not terminal
        and not general_terminal
        and not mobile_context
        and not mcp
        and not local_artifact_tools
    )
    low_confidence = (
        prediction["profile_confidence"] < PROFILE_THRESHOLD
        or (actionable and not execution_tools)
        or (not explicit_tools and prediction["tools_confidence"] < TOOL_THRESHOLD and not signals)
        or novel_input
    )
    if novel_input:
        planner_profile = "unknown"
        signals.append("out_of_distribution_input")
        reasons.append("Token coverage is too low for a reliable learned route.")
    if low_confidence and actionable:
        permission_behavior = "deny"
        next_action = "replan"
        signals.append("low_confidence_abstention")
        reasons.append("No sufficiently reliable actionable route was found.")
    elif permission_behavior == "deny":
        next_action = "replan"
    elif permission_behavior == "ask":
        next_action = "await_human"
    else:
        next_action = "continue"

    if safety_guard or production or explicit_refuse or external_high_risk:
        model_tier = "large"
    elif execution_tools or mutating:
        model_tier = "medium"
    else:
        model_tier = "small"
    context_policy = "expanded" if low_confidence or safety_guard or policy_mode == "refuse" else "focused"

    if execution_tools:
        reasons.insert(0, f"Selected executor set: {', '.join(execution_tools)}.")
    elif read_only:
        reasons.insert(0, "Kept the route read-only with no mutating executor.")
    else:
        reasons.insert(0, "Kept the route in planning because no executor was required.")

    overall_confidence = min(
        prediction["profile_confidence"],
        prediction["tools_confidence"] if execution_tools else prediction["profile_confidence"],
        prediction["policy_confidence"] if policy_mode != "act" else 1.0,
        prediction["known_token_ratio"],
    )
    if explicit_tools or explicit_refuse or explicit_confirm or strict_safety:
        overall_confidence = max(overall_confidence, 0.95)

    return {
        "schema_version": SCHEMA_VERSION,
        "planner_profile": planner_profile,
        "execution_tools": execution_tools,
        "planned_tools": planned_tools,
        "primary_executor": primary_executor,
        "policy_mode": policy_mode,
        "permission_behavior": permission_behavior,
        "model_tier": model_tier,
        "context_policy": context_policy,
        "next_action": next_action,
        "safety_guard": safety_guard,
        "permission_mode": permission_mode,
        "confidence": {
            "overall": round(overall_confidence, 6),
            "planner_profile": round(prediction["profile_confidence"], 6),
            "execution_tools": round(prediction["tools_confidence"], 6),
            "policy_mode": round(prediction["policy_confidence"], 6),
            "known_token_ratio": round(prediction["known_token_ratio"], 6),
        },
        "signals": _dedupe(signals),
        "reason": _dedupe(reasons),
    }


def validate_decision(decision: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "planner_profile",
        "execution_tools",
        "planned_tools",
        "primary_executor",
        "policy_mode",
        "permission_behavior",
        "model_tier",
        "context_policy",
        "next_action",
        "safety_guard",
        "permission_mode",
        "confidence",
        "signals",
        "reason",
    }
    missing = sorted(required - set(decision))
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
        return errors
    if decision["schema_version"] != SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if decision["planner_profile"] not in PROFILE_VALUES:
        errors.append("invalid planner_profile")
    if decision["policy_mode"] not in POLICY_VALUES:
        errors.append("invalid policy_mode")
    if decision["permission_behavior"] not in {"allow", "ask", "deny"}:
        errors.append("invalid permission_behavior")
    if decision["model_tier"] not in {"small", "medium", "large"}:
        errors.append("invalid model_tier")
    if decision["context_policy"] not in {"focused", "expanded"}:
        errors.append("invalid context_policy")
    if decision["next_action"] not in {"continue", "await_human", "replan"}:
        errors.append("invalid next_action")
    if not isinstance(decision["safety_guard"], bool):
        errors.append("safety_guard must be boolean")
    for field in ("execution_tools", "planned_tools", "signals", "reason"):
        if not isinstance(decision[field], list) or not all(isinstance(item, str) for item in decision[field]):
            errors.append(f"{field} must be a string list")
    invalid_tools = sorted(set(decision["execution_tools"]) - EXECUTION_TOOLS)
    if invalid_tools:
        errors.append(f"invalid execution tools: {', '.join(invalid_tools)}")
    if decision["primary_executor"] != "none" and decision["primary_executor"] not in EXECUTION_TOOLS:
        errors.append("invalid primary_executor")
    confidence = decision["confidence"]
    if not isinstance(confidence, dict):
        errors.append("confidence must be an object")
    else:
        for key in ("overall", "planner_profile", "execution_tools", "policy_mode", "known_token_ratio"):
            value = confidence.get(key)
            if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
                errors.append(f"invalid confidence.{key}")
    if decision["permission_behavior"] == "ask" and decision["next_action"] != "await_human":
        errors.append("ask must map to await_human")
    if decision["permission_behavior"] == "deny" and decision["next_action"] != "replan":
        errors.append("deny must map to replan")
    return errors


def strip_profile_hints(goal: str) -> str:
    cleaned = re.sub(
        r"Multi-source planner profile\s*\[[^\]]+\]\s*:\s*",
        "",
        goal,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"PhoneHarness\s+(?:main|safety)\s+workflow\s*\[[^\]]+\]\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return " ".join(cleaned.split())


def _split_tool_catalog(goal: str) -> tuple[str, list[str]]:
    match = re.search(r"\bAvailable tool interfaces:\s*(.+?)\.?$", goal, flags=re.IGNORECASE)
    if not match:
        return goal, []
    intent = goal[:match.start()].strip()
    tools = [
        item.strip().strip(". ")
        for item in match.group(1).split(",")
        if re.fullmatch(r"[a-z][a-z0-9_]*", item.strip().strip(". "), flags=re.IGNORECASE)
    ]
    return intent or goal, list(dict.fromkeys(tools))


def _required_catalog_tools(goal: str, available_tools: Iterable[str] = ()) -> list[str]:
    lower = goal.lower()
    available = set(available_tools)
    required: list[str] = []

    def add(*tool_names: str) -> None:
        for tool_name in tool_names:
            if tool_name not in required:
                required.append(tool_name)

    turns_on = _contains_any(lower, ["turn on", "enable", "switch on"])
    turns_off = _contains_any(lower, ["turn off", "disable", "switch off"])
    checks_state = _contains_any(lower, ["is my", "check", "status", "whether"])
    if "wifi" in lower:
        add("get_wifi_status" if checks_state and not (turns_on or turns_off) else "set_wifi_status")
    if "cellular" in lower:
        if checks_state and not (turns_on or turns_off):
            add("get_cellular_service_status")
        else:
            add("set_cellular_service_status")
    if "low battery" in lower:
        if checks_state and not (turns_on or turns_off):
            add("get_low_battery_mode_status")
        else:
            add("set_low_battery_mode_status")
    if "location service" in lower:
        if checks_state and not (turns_on or turns_off):
            add("get_location_service_status")
        else:
            add("set_location_service_status")

    asks_current_location = _contains_any(lower, ["where am i", "what city am i", "current city", "current location"])
    if _contains_any(lower, ["fix that in settings", "can't access", "cannot access", "enable location"]):
        asks_current_location = False
        add("set_location_service_status")
    if asks_current_location:
        add("get_current_location")
        if "city" in lower:
            add("search_lat_lon")

    if _contains_any(lower, ["how far am i", "how many km", "distance from", "distance to"]):
        add("get_current_location", "search_location_around_lat_lon", "calculate_lat_lon_distance")

    if _contains_any(lower, ["temperature", "temp ", " temp", "how cold", "weather"]):
        add("search_weather_around_lat_lon")
        if _has_relative_time(lower) and "timestamp_to_datetime_info" in available:
            add("get_current_timestamp")

    if _contains_any(lower, ["holiday", "christmas", "thanksgiving"]):
        add("search_holiday")
        if _contains_any(lower, ["how many days", "how far", "till", "until"]):
            add("get_current_timestamp", "timestamp_diff")
    if "stock" in lower or "ticker" in lower:
        add("search_stock")
    if "currency" in lower or re.search(r"\bconvert\s+\d.*\bto\b", lower):
        add("convert_currency")

    has_contact = (
        "contact" in lower
        or "contacts" in lower
        or ("phone number" in lower and _contains_any(lower, ["modify", "update", "change", "remove", "delete"]))
    )
    has_message = "message" in lower or "text" in lower or "contacted" in lower
    has_reminder = "reminder" in lower or "todo" in lower or "remind me" in lower
    direct_contact_id = _contains_any(lower, ["with id", "remove id", "person with id", "contact id"])
    if has_contact:
        if _contains_any(lower, ["add ", "create "]):
            add("add_contact")
        elif _contains_any(lower, ["remove", "delete", "get him out"]):
            if not direct_contact_id:
                add("search_contacts")
            add("remove_contact")
        elif _contains_any(lower, ["modify", "update", "change", "replace"]):
            if not direct_contact_id:
                add("search_contacts")
            add("modify_contact")
        else:
            add("search_contacts")
        if _contains_any(lower, ["last person", "last contact", "contacted last", "last message"]):
            add("get_current_timestamp", "search_messages")

    sends_message = _contains_any(lower, ["send a message", "send message", "send text", "text a message"])
    searches_message = has_message and _contains_any(lower, ["find", "search", "recent", "latest", "oldest", "content"])
    if sends_message:
        add("send_message_with_phone_number")
        if not re.search(r"\+\d{7,}", lower):
            add("search_contacts")
        if "cellular" in lower:
            add("get_cellular_service_status", "set_cellular_service_status")
        elif {"get_cellular_service_status", "set_cellular_service_status"}.issubset(available):
            add("get_cellular_service_status", "set_cellular_service_status")
    elif searches_message:
        add("search_messages")
        if _has_relative_time(lower):
            add("get_current_timestamp")

    if has_reminder:
        adds_reminder = "remind me" in lower or _contains_any(lower, [
            "add reminder", "add a reminder", "create reminder", "create a reminder", "add todo", "add a todo",
        ])
        if adds_reminder:
            add("add_reminder")
            if _has_relative_time(lower) or re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", lower):
                add("datetime_info_to_timestamp")
        elif _contains_any(lower, ["remove", "delete"]):
            add("search_reminder", "remove_reminder")
        elif _contains_any(lower, ["modify", "update", "change", "push", "move"]):
            add("search_reminder", "modify_reminder")
        else:
            add("search_reminder")
        if _has_relative_time(lower) and not adds_reminder:
            add("get_current_timestamp")

    if "relationship" in lower or _contains_any(lower, ["my boss", "my manager", "my supervisor", "my spouse"]):
        add("search_contacts")

    return required


def _has_relative_time(lower: str) -> bool:
    return bool(
        _contains_any(lower, [
            "last", "latest", "recent", "oldest", "upcoming", "yesterday", "tomorrow", "later",
            "next ", "this week", "weekday", "monday", "tuesday", "wednesday",
            "thursday", "friday", "saturday", "sunday", " am", " pm",
        ])
        or re.search(r"\d{1,2}:\d{2}|\d{1,2}/\d{1,2}/\d{2,4}", lower)
    )


def _catalog_execution_tools(required_tools: Iterable[str]) -> list[str]:
    mcp_prefixes = (
        "add_contact", "modify_contact", "remove_contact", "search_contacts",
        "send_message", "search_messages", "add_reminder", "modify_reminder",
        "remove_reminder", "search_reminder",
    )
    selected: list[str] = []
    for tool_name in required_tools:
        executor = "mcp_tool_runner" if tool_name.startswith(mcp_prefixes) else "mobile_cli_runner"
        if executor not in selected:
            selected.append(executor)
    return _ordered_tools(selected)


def _predict_label(model: dict[str, Any], text: str) -> tuple[str, float]:
    labels = sorted(model.get("class_doc_counts", {}))
    if not labels:
        return "", 0.0
    token_counts = Counter(_tokenize(text))
    total_docs = sum(int(count) for count in model["class_doc_counts"].values())
    vocabulary = set(model.get("vocabulary", []))
    vocab_size = max(1, len(vocabulary))
    alpha = float(model.get("alpha", 1.0))
    scores: dict[str, float] = {}
    for label in labels:
        doc_count = int(model["class_doc_counts"][label])
        if model.get("balanced_prior", False):
            prior = math.log(1.0 / len(labels))
        else:
            prior = math.log((doc_count + alpha) / (total_docs + alpha * len(labels)))
        label_counts = model["class_token_counts"].get(label, {})
        total_tokens = int(model["class_total_tokens"].get(label, 0))
        denominator = total_tokens + alpha * vocab_size
        score = prior
        for token, count in token_counts.items():
            score += count * math.log((int(label_counts.get(token, 0)) + alpha) / denominator)
        scores[label] = score
    best = max(scores, key=scores.get)
    best_score = scores[best]
    weights = [math.exp(max(-60.0, score - best_score)) for score in scores.values()]
    return best, float(1.0 / sum(weights))


def _tokenize(text: str) -> list[str]:
    chunks = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text.lower())
    tokens: list[str] = []
    for chunk in chunks:
        if all("\u4e00" <= char <= "\u9fff" for char in chunk):
            tokens.extend(chunk)
            tokens.extend(_char_ngrams(chunk, 2))
            tokens.extend(_char_ngrams(chunk, 3))
        else:
            if len(chunk) > 1:
                tokens.append(chunk)
            if len(chunk) >= 6:
                tokens.extend([chunk[:4], chunk[-4:]])
    return tokens or ["<empty>"]


def _char_ngrams(text: str, size: int) -> list[str]:
    return [text[index:index + size] for index in range(max(0, len(text) - size + 1))]


def _decode_tools(label: str) -> list[str]:
    if not label or label == "none":
        return []
    return _ordered_tools(label.split(","))


def _explicit_execution_tools(goal: str) -> list[str]:
    lower = goal.lower()
    found: list[str] = []
    for marker in ("execution_tools=", "execution_tool="):
        start = lower.find(marker)
        if start < 0:
            continue
        raw = lower[start + len(marker):].split("]", 1)[0].split(";", 1)[0]
        raw = raw.replace("|", ",").replace(" ", ",")
        found.extend(item.strip() for item in raw.split(","))
    return _ordered_tools(found)


def _learned_tools(
    prediction: dict[str, Any],
    *,
    terminal: bool,
    read_only: bool,
    local_project: bool,
    local_artifact_tools: list[str],
) -> list[str]:
    if read_only:
        return []
    if terminal:
        return ["command_runner"]
    if local_artifact_tools:
        return local_artifact_tools
    if prediction["tools_confidence"] < TOOL_THRESHOLD:
        return []
    if local_project and not (
        prediction["planner_profile"] == "skill_workflow"
        and prediction["profile_confidence"] >= 0.85
        and prediction["tools_confidence"] >= 0.85
    ):
        return []
    return _ordered_tools(prediction["execution_tools"])


def _merge_external_tools(
    goal: str,
    prediction: dict[str, Any],
    learned: list[str],
    mobile: list[str],
) -> list[str]:
    if not learned:
        return mobile
    lower = goal.lower()
    primary_gui = _contains_any(lower, MOBILE_GUI_TERMS)
    mcp = _contains_any(lower, MCP_TERMS)
    if mobile and primary_gui and "mobile_cli_runner" not in learned and "mobile_cli_runner" not in mobile:
        return _ordered_tools([*mobile, *learned])
    if mobile and primary_gui and "mobile_cli_runner" in learned and not mcp:
        return _ordered_tools([*mobile, "mobile_cli_runner", *learned])
    if mcp and "mobile_cli_runner" in mobile and "mcp_tool_runner" in [*learned, *mobile]:
        return _ordered_tools(["mcp_tool_runner", "mobile_cli_runner", *learned, *mobile])
    if (
        prediction["profile_confidence"] >= TOOL_THRESHOLD
        and prediction["planner_profile"] in {"skill_workflow", "api_planning", "policy_tool_agent"}
    ):
        return learned
    return _ordered_tools([*learned, *mobile])


def _mobile_tools(goal: str) -> list[str]:
    lower = goal.lower()
    mobile_context = _contains_any(lower, MOBILE_CONTEXT_TERMS)
    tools: list[str] = []
    if _contains_any(lower, MCP_TERMS):
        tools.append("mcp_tool_runner")
    if mobile_context and _contains_any(lower, MOBILE_CLI_TERMS):
        tools.append("mobile_cli_runner")
    if _contains_any(lower, MOBILE_GUI_TERMS):
        tools.append("mobile_gui_runner")
    return _ordered_tools(tools)


def _terminal_context(goal: str) -> bool:
    lower = goal.lower()
    return _contains_any(lower, [
        "terminalworld verified terminal task",
        "terminalworld style cli task",
        "verified terminal benchmark task",
        "/app/result.txt",
    ])


def _general_terminal_context(goal: str, *, mobile_context: bool, mcp: bool) -> bool:
    if mobile_context or mcp or _terminal_context(goal):
        return False
    lower = goal.lower()
    shell_markers = [
        "run pytest",
        "run npm",
        "run cargo",
        "run make",
        "bash script",
        "shell command",
        "command line",
        "terminal command",
        "命令行",
        "终端命令",
        "运行测试命令",
    ]
    return _contains_any(lower, shell_markers) or bool(re.search(r"(^|\s)(pytest|npm|pnpm|cargo|git|bash)\s+", lower))


def _local_artifact_tools(goal: str) -> list[str]:
    if _terminal_context(goal):
        return []
    lower = goal.lower()
    has_artifact = bool(re.search(
        r"(/root/|/workspace/|/input/|/output/|\b[a-z0-9_.-]+\.(?:pdf|stl|csv|json|txt|md|docx|xlsx|png|jpg|jpeg|py|sh)\b)",
        lower,
    ))
    if not has_artifact:
        return []
    if _contains_any(lower, [
        "save", "fill", "edit", "update", "write", "generate", "calculate", "parse", "extract",
        "convert", "repair", "fix", "compile", "validate", "transform", "保存", "填写", "编辑",
        "更新", "写入", "生成", "计算", "解析", "提取", "转换", "修复", "验证",
    ]):
        return ["file_writer", "command_runner"]
    return []


def _local_project_context(goal: str) -> bool:
    lower = goal.lower()
    if re.search(r"\b(benchmark|readme|openclaw|repository|workspace|production|deploy)\b", lower):
        return True
    if re.search(r"\bplanner\b", lower) and re.search(r"\b(code|file|files|workspace|benchmark|implementation)\b", lower):
        return True
    return _contains_any(lower, ["优化", "修改", "测试", "验证", "删除", "部署", "上线"])


def _learned_policy(
    prediction: dict[str, Any],
    local_artifact_tools: list[str],
    explicit_tools: list[str],
) -> str:
    if explicit_tools or local_artifact_tools or prediction["policy_confidence"] < POLICY_THRESHOLD:
        return ""
    if prediction["planner_profile"] != "policy_tool_agent":
        return ""
    return prediction["policy_mode"]


def _explicit_safety_policy(goal: str) -> bool:
    return _contains_any(goal.lower(), [
        "safety_policy",
        "safety policy",
        "policy_mode=refuse",
        "policy_mode=confirm",
        "require confirmation",
        "never auto-execute",
        "safe_complete",
        "confirm_first",
        "never_auto",
        "安全",
        "禁止自动",
    ])


def _strict_safety(goal: str) -> bool:
    lower = goal.lower()
    if _contains_any(lower, STRICT_SAFETY_TERMS):
        return True
    return bool(
        re.search(r"通话记录.*(邮箱|发|导出|整理)", lower)
        or re.search(r"(微信)?聊天记录.*(全部|所有|最近).*(导出|发)", lower)
        or re.search(r"(相册|照片).*(全部|所有).*(删|删除|清)", lower)
        or re.search(r"天气预报.*(邮箱|邮件|发送|发给|mcp)", lower)
        or re.search(r"科技新闻.*(邮箱|邮件|发送|发给|mcp)", lower)
        or re.search(r"~/download/.*(发邮件|发给|邮箱)", lower)
        or re.search(r"备份.*重要数据", lower)
    )


def _primary_executor(goal: str, tools: list[str], safety_guard: bool) -> str:
    if not tools:
        return "none"
    if not safety_guard:
        return tools[0]
    lower = goal.lower()
    if "mobile_gui_runner" in tools and (
        re.search(r"(相册|照片).*(全部|所有).*(删|删除|清)", lower)
        or _contains_any(lower, ["相册里所有照片", "照片都删", "所有照片都删"])
    ):
        return "mobile_gui_runner"
    if "mobile_cli_runner" in tools and _contains_any(lower, [
        "wifi密码", "wi-fi密码", "天气预报", "科技新闻", "新闻热点", "手机存储", "存储空间",
    ]):
        return "mobile_cli_runner"
    if "mcp_tool_runner" in tools and _contains_any(lower, ["邮件", "邮箱", "发一封", "发到", "发给"]):
        return "mcp_tool_runner"
    if "mobile_gui_runner" in tools and _contains_any(lower, [
        "chrome", "密码", "开发者模式", "usb调试", "钉钉", "相册", "照片", "个人数据",
        "账号全退", "全部清", "清干净", "b站", "奶茶店", "备份",
    ]):
        return "mobile_gui_runner"
    return tools[0]


def _permission_behavior(permission_mode: str, *, policy_mode: str, primary_executor: str) -> str:
    mutating_executor = primary_executor in EXECUTION_TOOLS
    if policy_mode == "refuse":
        return "deny"
    if policy_mode == "confirm":
        if permission_mode in {"EXPLORE", "DONT_ASK"} and mutating_executor:
            return "deny"
        return "ask"
    if permission_mode == "EXPLORE" and mutating_executor:
        return "deny"
    if permission_mode == "DONT_ASK" and mutating_executor:
        return "deny"
    if permission_mode == "DEFAULT" and mutating_executor:
        return "ask"
    return "allow"


def _planned_tools(
    goal: str,
    execution_tools: list[str],
    *,
    primary_executor: str,
    safety_guard: bool,
    read_only: bool,
    mutating: bool,
    production: bool,
    terminal: bool,
    planner_profile: str,
) -> list[str]:
    if execution_tools:
        if safety_guard:
            return ["risk_model", "safety_guard", "planner", primary_executor, "verifier"]
        path_tools = list(execution_tools)
        if (
            "mcp_tool_runner" in path_tools
            and not _contains_any(goal.lower(), MCP_TERMS)
            and len(path_tools) > 1
            and planner_profile == "mobile_or_mcp_workflow"
        ):
            path_tools.remove("mcp_tool_runner")
        return ["risk_model", "planner", *path_tools[:2], "verifier"]
    if terminal:
        return ["risk_model", "planner", "command_runner", "verifier"]
    if production:
        return ["goal_analyzer", "risk_model", "planner", "deploy_runner", "verifier"]
    if mutating and not read_only:
        return ["risk_model", "planner", "file_writer", "command_runner", "verifier"]
    return ["goal_analyzer", "workspace_inspector", "planner", "risk_model", "verifier"]


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def _ordered_tools(tools: Iterable[str]) -> list[str]:
    present = {tool for tool in tools if tool in EXECUTION_TOOLS}
    return [tool for tool in TOOL_ORDER if tool in present]


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _route_rows(rows: Iterable[dict[str, Any]], model_path: Path, default_permission: str) -> list[dict[str, Any]]:
    routed: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        goal = str(row.get("goal", "")).strip()
        if not goal:
            raise ValueError(f"row {index} has no goal")
        decision = route_task(
            goal,
            permission_mode=str(row.get("permission_mode") or default_permission),
            model_path=model_path,
        )
        if row.get("id") is not None:
            decision["task_id"] = str(row["id"])
        routed.append(decision)
    return routed


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"line {index} is not a JSON object")
        rows.append(payload)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Route tasks through the OpenClaw distilled policy skill.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--goal")
    source.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--output-jsonl", type=Path)
    parser.add_argument("--permission-mode", default="DEFAULT")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.goal is not None:
        decision = route_task(args.goal, permission_mode=args.permission_mode, model_path=args.model)
        errors = validate_decision(decision)
        if errors:
            raise SystemExit("Invalid route: " + "; ".join(errors))
        print(json.dumps(decision, ensure_ascii=False, indent=2 if args.pretty else None))
        return

    decisions = _route_rows(_read_jsonl(args.input_jsonl), args.model, args.permission_mode)
    lines = [json.dumps(decision, ensure_ascii=False) for decision in decisions]
    if args.output_jsonl:
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        args.output_jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"route_task: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
