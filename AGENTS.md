# Repository Guidance

- Keep `SKILL.md` concise and agent-facing; put research detail in `docs/` or `references/`.
- Runtime code must remain Python-standard-library only and offline.
- Never add raw benchmark prompts, credentials, private logs, or executable model formats.
- Add positive and negative routing tests for behavior changes.
- Run `python3 -m unittest discover -s tests -v`, `python3 scripts/validate_skill.py .`, and `python3 scripts/verify_release.py .` before completion.
- Do not claim promotion from training accuracy alone; preserve dev/holdout separation and the published gates.
