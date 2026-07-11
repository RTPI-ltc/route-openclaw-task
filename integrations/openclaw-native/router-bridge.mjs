import { execFile } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const MODULE_ROOT = dirname(fileURLToPath(import.meta.url));
const DEFAULTS = Object.freeze({
  enabled: true,
  pythonBin: "python3",
  timeoutMs: 1500,
  maxPromptChars: 12000,
});
const ROUTE_FIELDS = [
  "schema_version",
  "planner_profile",
  "planned_tools",
  "primary_executor",
  "policy_mode",
  "permission_behavior",
  "context_policy",
  "model_tier",
  "next_action",
  "safety_guard",
  "confidence",
  "reason",
];

export function normalizeConfig(value = {}) {
  const raw = value && typeof value === "object" ? value : {};
  return {
    enabled: raw.enabled !== false,
    pythonBin: nonEmptyString(raw.pythonBin, DEFAULTS.pythonBin),
    timeoutMs: boundedInteger(raw.timeoutMs, 100, 5000, DEFAULTS.timeoutMs),
    maxPromptChars: boundedInteger(raw.maxPromptChars, 256, 32000, DEFAULTS.maxPromptChars),
  };
}

export async function routePrompt(prompt, options = {}) {
  const config = normalizeConfig(options.config);
  if (!config.enabled || typeof prompt !== "string" || !prompt.trim()) {
    return null;
  }
  const pluginRoot = options.pluginRoot || MODULE_ROOT;
  const script = join(pluginRoot, "skills", "task-compass", "scripts", "route_task.py");
  const goal = prompt.slice(0, config.maxPromptChars);
  const { stdout } = await execFileAsync(config.pythonBin, [script, "--goal", goal], {
    cwd: join(pluginRoot, "skills", "task-compass"),
    timeout: config.timeoutMs,
    maxBuffer: 1024 * 1024,
    windowsHide: true,
    env: {
      LANG: "C.UTF-8",
      PATH: process.env.PATH || "",
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONIOENCODING: "utf-8",
    },
  });
  const decision = JSON.parse(stdout);
  if (decision?.schema_version !== "1.0") {
    throw new Error("task-compass returned an unsupported schema version");
  }
  return decision;
}

export function buildRouteContext(decision) {
  const bounded = {};
  for (const field of ROUTE_FIELDS) {
    if (Object.hasOwn(decision, field)) {
      bounded[field] = decision[field];
    }
  }
  return [
    "<task-compass advisory=\"true\">",
    JSON.stringify(bounded),
    "Preserve refuse, await_human, replan, confirmation, read-only, and safety constraints. OpenClaw runtime permissions remain authoritative.",
    "</task-compass>",
  ].join("\n");
}

function boundedInteger(value, min, max, fallback) {
  return Number.isInteger(value) && value >= min && value <= max ? value : fallback;
}

function nonEmptyString(value, fallback) {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}
