# Vendored third-party skills

Claude Code cloud sessions don't install plugins (not even ones enabled in
`.claude/settings.json`), so these are copied into the repo. Both are MIT; each
keeps its `LICENSE`.

| Skill | Upstream | Commit | Date |
|---|---|---|---|
| `taste-skill/` | https://github.com/leonxlnx/taste-skill (`skills/taste-skill`) | `63aba5f` | 2026-10-20 |
| `seo/`, `seo-*/`, `../agents/*.md` | https://github.com/AgriciDaniel/claude-seo (v2.4.2) | `4b99de2` | 2026-10-05 |

## Local patches
- **claude-seo:** laid out like its own `install.sh` manual install (runtime
  scripts, schema, data, hooks, `requirements.txt`, `runtime-plugin.json` under
  `seo/`). `${CLAUDE_PLUGIN_ROOT}` is rewritten to repo-relative paths: the
  launcher becomes `"$(git rev-parse --show-toplevel)/.claude/skills/seo/scripts/claude-seo"`
  and sub-skill references `.claude/skills/<name>/`. Paid-API `extensions/` and
  the `seo-cockpit` plugin are not included. Its PostToolUse schema hook is
  copied but not wired up.
- **taste-skill:** `scripts/lib/cdp.mjs` adds `--no-sandbox` when running as
  root, which Chrome requires in cloud containers.

## Updating
Re-copy from upstream, re-apply the patches above, and update the table.
