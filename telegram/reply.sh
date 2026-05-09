#!/usr/bin/env bash
# Send a Telegram reply via the spiral 3d bot.
#
# Reads TELEGRAM_BOT_TOKEN from this dir's .env. Reads chat IDs from approved/
# (one file per paired senderId, file contents = chat_id). For text replies
# only — attachments take more work, add later if needed.
#
# Usage:
#   ./reply.sh <senderId> <message text...>
#   ./reply.sh <senderId> -      # read message text from stdin

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
env_file="$here/.env"
approved="$here/approved"

[[ -f "$env_file" ]] || { echo "no .env at $env_file" >&2; exit 1; }
# shellcheck disable=SC1090
source "$env_file"
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN missing in .env}"

sender="${1:?missing senderId}"
shift || true

chat_file="$approved/$sender"
if [[ -f "$chat_file" ]]; then
  chat_id="$(cat "$chat_file")"
else
  # Bot consumes approved/<senderId> after the pairing confirmation, so the
  # file usually isn't there. For DMs Telegram chat_id == user_id, so fall
  # back to that. (Won't work for groups — pass the group's chat_id explicitly.)
  chat_id="$sender"
fi

if [[ "${1:-}" == "-" ]]; then
  text="$(cat)"
else
  text="$*"
fi

[[ -n "$text" ]] || { echo "empty message" >&2; exit 2; }

resp=$(curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${chat_id}" \
  --data-urlencode "text=${text}")
node -e 'const r=process.argv[1]; try { const j=JSON.parse(r); if(!j.ok){console.error("telegram error:",j); process.exit(1)} console.log("sent message_id="+j.result.message_id) } catch(e) { console.error("non-JSON response from Telegram:"); console.error(r); process.exit(1) }' "$resp"
