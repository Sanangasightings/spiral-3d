#!/usr/bin/env bash
# Project-local pairing helper for the spiral 3d telegram channel.
#
# The plugin's /telegram:access skill is hardcoded to ~/.claude/channels/telegram/access.json
# (chronotope). This script is the equivalent for this project, operating ONLY on
# the access.json next to it. Never points at chronotope.
#
# Usage:
#   ./pair.sh                  # show status
#   ./pair.sh pair <code>      # redeem a pending pairing code
#   ./pair.sh allow <senderId> # add senderId to allowFrom directly
#   ./pair.sh deny <code>      # drop a pending entry
#   ./pair.sh policy <mode>    # pairing | allowlist | disabled

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
access="$here/access.json"
approved="$here/approved"

mkdir -p "$approved"
[[ -f "$access" ]] || echo '{"dmPolicy":"pairing","allowFrom":[],"groups":{},"pending":{}}' > "$access"

cmd="${1:-status}"

case "$cmd" in
  status)
    node -e '
      const a = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8"));
      console.log("dmPolicy:", a.dmPolicy);
      console.log("allowFrom:", a.allowFrom.length, "->", a.allowFrom.join(", ") || "(none)");
      const pend = Object.entries(a.pending || {});
      console.log("pending:", pend.length);
      for (const [code, p] of pend) {
        const age = Math.round((Date.now() - p.createdAt) / 1000);
        console.log("  " + code + " sender=" + p.senderId + " age=" + age + "s");
      }
      console.log("groups:", Object.keys(a.groups || {}).length);
    ' "$access"
    ;;
  pair)
    code="${2:?missing code}"
    node -e '
      const fs = require("fs");
      const path = require("path");
      const accessFile = process.argv[1];
      const approvedDir = process.argv[2];
      const code = process.argv[3];
      const a = JSON.parse(fs.readFileSync(accessFile, "utf8"));
      const p = (a.pending || {})[code];
      if (!p) { console.error("no pending entry for code: " + code); process.exit(2); }
      if (p.expiresAt && p.expiresAt < Date.now()) { console.error("code expired"); process.exit(2); }
      a.allowFrom = Array.from(new Set([...(a.allowFrom || []), p.senderId]));
      delete a.pending[code];
      fs.writeFileSync(accessFile, JSON.stringify(a, null, 2) + "\n");
      fs.mkdirSync(approvedDir, { recursive: true });
      fs.writeFileSync(path.join(approvedDir, p.senderId), p.chatId);
      console.log("paired senderId=" + p.senderId + " chatId=" + p.chatId);
    ' "$access" "$approved" "$code"
    ;;
  deny)
    code="${2:?missing code}"
    node -e '
      const fs = require("fs");
      const a = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
      delete (a.pending || {})[process.argv[2]];
      fs.writeFileSync(process.argv[1], JSON.stringify(a, null, 2) + "\n");
      console.log("denied " + process.argv[2]);
    ' "$access" "$code"
    ;;
  allow)
    sender="${2:?missing senderId}"
    node -e '
      const fs = require("fs");
      const a = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
      a.allowFrom = Array.from(new Set([...(a.allowFrom || []), process.argv[2]]));
      fs.writeFileSync(process.argv[1], JSON.stringify(a, null, 2) + "\n");
      console.log("allowed " + process.argv[2]);
    ' "$access" "$sender"
    ;;
  policy)
    mode="${2:?missing mode}"
    case "$mode" in pairing|allowlist|disabled) ;; *) echo "mode must be pairing|allowlist|disabled" >&2; exit 2 ;; esac
    node -e '
      const fs = require("fs");
      const a = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
      a.dmPolicy = process.argv[2];
      fs.writeFileSync(process.argv[1], JSON.stringify(a, null, 2) + "\n");
      console.log("dmPolicy=" + process.argv[2]);
    ' "$access" "$mode"
    ;;
  *)
    echo "unknown command: $cmd" >&2
    echo "usage: $0 [status|pair <code>|deny <code>|allow <senderId>|policy <mode>]" >&2
    exit 2
    ;;
esac
