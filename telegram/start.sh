#!/usr/bin/env bash
# Launch the spiral 3d Telegram bot pointed at this project's state dir.
# The plugin server respects TELEGRAM_STATE_DIR — same code, different state,
# fully insulated from ~/.claude/channels/telegram (chronotope).

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
server="$here/server/server.ts"

if [[ ! -f "$server" ]]; then
  echo "spiral telegram: server.ts not found at $server" >&2
  echo "did you copy it from the plugin and run bun install?" >&2
  exit 1
fi

export TELEGRAM_STATE_DIR="$here"
echo "spiral telegram: state dir = $here"
echo "spiral telegram: starting (Ctrl+C to stop)..."

# server.ts shuts down on stdin EOF (it's an MCP server expecting Claude Code
# to hold stdio open). Standalone, we pipe a never-closing source so the
# shutdown handler never fires and the bot poller stays alive.
cd "$here/server" && tail -f /dev/null | exec bun "$server"
