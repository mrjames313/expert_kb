# Hooks

Three shell scripts that Claude Code can invoke at session lifecycle events. They keep the framework's on-disk state consistent across sessions — particularly the pulse log → pulse.md compaction.

The hooks are optional. Skills do everything they need to do (`/start` loads orientation, `/wrap-up` compacts pulse, runs lint, records telemetry). Hooks add belt-and-suspenders: orientation files surface automatically at the start of a session, and pulse state is preserved even when an agent exits without invoking `/wrap-up`.

## The scripts

| Hook | Fires when | What it does |
|---|---|---|
| `session-start.sh` | A Claude Code session begins | Prints CLAUDE.md, areas-index.md, and INBOX.md to stdout so the agent has the project shape in context. Warns about uncompacted pulse logs from a prior session and notes any orphan telemetry session marker. Resets this session's state file (`_session/<session-id>.json` — role/area cleared, identity stamped), sweeps files left by dead sessions, and refreshes the status line's vitals cache. |
| `session-end.sh` | A Claude Code session ends | If pulse logs are non-empty, runs `pulse_compact.py`. If a telemetry session marker exists, records a `session_end` event (with no citation/load data — the agent isn't around to ask). Retires this session's state file. |
| `pre-compact.sh` | Before Claude Code compacts the conversation context | Same as session-end except it doesn't record a session_end event (the session is still going). Flushes pulse to disk so it survives compaction. |
| `statusline.sh` | On every status-line render | Prints a compact status line via `statusline.py`: `<project> · <role@area> · H<n\|✓> R<n\|✓\|–> · ctx <N>k[!] · run /kb-vitals`. **H** = what the human owes project-wide, **R** = the adopted role's hygiene (`–` when no role is adopted); green clear, yellow hygiene, red blocking. `!` marks a context past the restart threshold, and the `run /kb-vitals` hint appears only when something is pending. Cheap: ~0.6ms of scanning: fast-moving vitals live, the expensive three from `_framework/telemetry/vitals-cache.json`, no `yaml`, no KB walk. Wired via the `statusLine` key in `.claude/settings.json` (not the `hooks` block). |

All scripts are best-effort. They never fail the session — any error is logged to stderr and ignored, and the status line prints nothing on trouble.

## Installation in Claude Code

Hooks are wired up in your Claude Code settings. The standard locations:

- `.claude/settings.json` — committed to the repo; shared with collaborators (**use this**).
- `.claude/settings.local.json` — gitignored; for your own machine.
- `~/.claude/settings.json` — user-wide; applies to all your projects.

The framework ships with `.claude/settings.json` already configured at the repo root, so the hooks should be active after you clone. The file contains:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/_framework/hooks/session-start.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/_framework/hooks/session-end.sh"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/_framework/hooks/pre-compact.sh"
          }
        ]
      }
    ]
  }
}
```

A few details about this format:

- The outer key (`SessionStart` etc.) is the **event** name.
- Each event holds an array of **matcher groups**. We omit `matcher` to fire on every occurrence.
- Each matcher group holds a `hooks` array of **handlers**. A handler has a `type` and (for shell hooks) a `command`.
- `$CLAUDE_PROJECT_DIR` is a placeholder Claude Code substitutes with your project root, so the same settings file works regardless of cwd.

To verify the hooks are active, run `/hooks` inside Claude Code — it opens a read-only browser showing all configured hooks and where each one came from.

## Disabling hooks

To stop a specific hook firing, comment it out or delete its entry in `.claude/settings.json`. To temporarily disable all hooks without editing settings, set `"disableAllHooks": true` at the top level of the settings file.

If you're using `.claude/settings.local.json` for personal overrides, you can add a disabled hook entry there to override the project-level config.

## Testing the hooks manually

You can run any hook directly to see what it does:

```bash
bash _framework/hooks/session-start.sh
bash _framework/hooks/session-end.sh
bash _framework/hooks/pre-compact.sh
```

`session-start.sh` is the chatty one — it dumps the three orientation files plus a state summary. The others are nearly silent unless they have actual work to do (compacting a non-empty pulse log).

## Making them executable

If your filesystem stores executable bits and Claude Code invokes scripts directly (without `bash` prefix), you may need:

```bash
chmod +x _framework/hooks/*.sh
```

If you're invoking via `bash <script>` in your settings.json (as shown above), this isn't necessary.

## Customization

The hooks are short — ~50–80 lines each. Edit them freely. Common adjustments:

- **Skip the INBOX.md surfacing in session-start** if you find it noisy: comment out the INBOX.md block.
- **Skip auto-compaction in session-end** if you want every session to require explicit `/wrap-up`: comment out the `pulse_compact.py` invocation.
- **Add area-specific surfacing** in session-start: e.g., cat `commons/POR.md` automatically if `por` is enabled.

The hooks intentionally don't read `_framework/config.yml`; they do the same thing regardless of which capabilities are on. If you want conditional behavior, add a Python helper or just edit the hook directly.

## What hooks deliberately don't do

- **Adopt a role.** The `/start` skill does that. Hooks just stage context for the skill.
- **Record `session_start` telemetry.** The agent does that when it adopts a role — the hook can't know which role yet.
- **Track citations.** Only the agent knows what it cited; hooks fire when no agent is in conversation.
- **Invoke skills.** Skills are agent-facing — they require an agent to interpret them. Hooks can call deterministic tools (`pulse_compact.py`, `telemetry.py`) but not `/wrap-up`.

In other words: the hooks deal with on-disk state. The skills deal with agent state. The two layers don't overlap.
