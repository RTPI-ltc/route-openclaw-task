import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { buildRouteContext, routePrompt } from "./router-bridge.mjs";

export default definePluginEntry({
  id: "task-compass",
  name: "Task Compass Skill",
  description: "Injects a deterministic advisory route before prompt construction.",
  register(api) {
    api.on(
      "before_prompt_build",
      async (event) => {
        try {
          const decision = await routePrompt(event.prompt, { config: api.pluginConfig });
          if (!decision) {
            return;
          }
          return { appendContext: buildRouteContext(decision) };
        } catch (error) {
          api.logger.warn?.(
            `task-compass: router unavailable; using baseline planner (${errorCategory(error)})`,
          );
          return;
        }
      },
      { priority: 20, timeoutMs: 5500 },
    );
  },
});

function errorCategory(error) {
  if (error instanceof SyntaxError) {
    return "invalid-json";
  }
  if (error && typeof error === "object") {
    if (error.killed === true) {
      return "timeout";
    }
    if (error.code === "ENOENT") {
      return "python-unavailable";
    }
  }
  return "router-error";
}
