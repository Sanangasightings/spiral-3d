#!/usr/bin/env bash
# List unread .md inbox files (text messages from the spiral bot) newest-first.
# Use the path returned to Read the message body; once handled, mv it into
# inbox/_read/ so it doesn't show up again.
#
# Usage:
#   ./read-inbox.sh                  # list pending text messages
#   ./read-inbox.sh ack <filename>   # mark one message as read

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
inbox="$here/inbox"
read_dir="$here/inbox/_read"

mkdir -p "$inbox" "$read_dir"

cmd="${1:-list}"

case "$cmd" in
  list)
    # .md files only (text). Attachments (.jpg, .docx, etc.) are not unread-tracked here.
    found=0
    while IFS= read -r f; do
      found=1
      echo "$f"
    done < <(ls -1t "$inbox"/*.md 2>/dev/null || true)
    if [[ $found -eq 0 ]]; then
      echo "(no pending text messages)"
    fi
    ;;
  ack)
    name="${2:?missing filename}"
    src="$inbox/$name"
    [[ -f "$src" ]] || { echo "no such file: $src" >&2; exit 2; }
    mv "$src" "$read_dir/"
    echo "moved to _read/"
    ;;
  *)
    echo "usage: $0 [list|ack <filename>]" >&2
    exit 2
    ;;
esac
