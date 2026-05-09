#!/usr/bin/env bash
# Background watcher: polls inbox/ every 1s and prints "NEW: <path>" for each
# previously-unseen file at the top level. Used as the source command for the
# Monitor tool so Claude gets pinged the moment a Telegram message lands.
#
# State: ./.notified/<name> — empty marker file per notified inbox file.
# Pruned when the source file is gone (e.g. moved to inbox/_read by ack).

set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"
mkdir -p .notified inbox

# Disable buffering so each line reaches Monitor immediately.
exec stdbuf -oL -eL bash -c '
  while true; do
    for f in inbox/*; do
      [[ -f "$f" ]] || continue
      name="$(basename "$f")"
      if [[ ! -e ".notified/$name" ]]; then
        echo "NEW: $f"
        touch ".notified/$name"
      fi
    done
    for m in .notified/*; do
      [[ -e "$m" ]] || continue
      [[ -e "inbox/$(basename "$m")" ]] || rm -f "$m"
    done
    sleep 1
  done
'
