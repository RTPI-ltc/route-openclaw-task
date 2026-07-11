# Claude Code integration

This package follows the Claude Code plugin layout with
`.claude-plugin/plugin.json` and `skills/route-openclaw-task/SKILL.md`.

Supported contract range: Claude Code `>=2.1.142 <3.0.0`. The manifest schema
snapshot is hash-locked in `../compatibility.json`. Per the project owner's
constraint, Claude Code is not installed or started. The release performs an
offline manifest/layout contract check and executes the embedded router across
the integration benchmark; it does not claim a native Claude runtime test.
