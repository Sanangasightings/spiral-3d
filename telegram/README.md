# Spiral 3d Telegram channel

Project-local, fully insulated from the chronotope channel at
`~/.claude/channels/telegram/`. Same plugin server code, different state
directory — set via `TELEGRAM_STATE_DIR=$(pwd)` when launching.

## Files

| File | Purpose |
|------|---------|
| `.env` | `TELEGRAM_BOT_TOKEN` for the spiral bot. **Gitignored.** |
| `access.json` | `dmPolicy` + `allowFrom` + `pending` for this bot only |
| `approved/<senderId>` | Per-paired-user file, contents = chat_id |
| `inbox/` | Bot-dropped attachments (jpg, md, etc.) |
| `bot.pid` | Runtime PID, written by the server |
| `start.ps1` / `start.sh` | Launch the bot pointed at this dir |
| `pair.sh` | Project-local equivalent of `/telegram:access` (operates on **this** access.json, not chronotope's) |
| `reply.sh` | Send a text reply to a paired sender via the Telegram Bot API |

## Start the bot

PowerShell:

```powershell
cd "C:\Users\Owner\Documents\Claude\Projects\spiral 3d\telegram"
.\start.ps1
```

Bash:

```bash
cd "/c/Users/Owner/Documents/Claude/Projects/spiral 3d/telegram"
./start.sh
```

The server prints the resolved state dir on startup — confirm it ends in
`spiral 3d/telegram` and not `~/.claude/channels/telegram`.

## Pair your Telegram account

1. Start the bot (above).
2. DM the bot from Telegram. It will reply with a 6-character pairing code.
3. In your terminal at this folder, run:

   ```bash
   ./pair.sh status            # see the pending code
   ./pair.sh pair <code>       # redeem it
   ```

   Or directly: `./pair.sh allow <yourSenderId>` if you already know your
   Telegram numeric user ID and want to skip pairing.

4. The bot drops a "you're in" message back to you when the `approved/`
   entry lands.

## Reply from Claude

Claude reads incoming messages from `inbox/` (attachments) and pushes them
through the MCP plugin (text). For *this* channel the MCP tools won't
work — they're wired to chronotope. To send a text reply through the
spiral bot, Claude runs:

```bash
./reply.sh <senderId> "message text"
```

`<senderId>` is the file name under `approved/`.

## Why this is separate

`server.ts` honors `TELEGRAM_STATE_DIR` (line 26 of the plugin). Setting
it to this folder gives the same code a different `access.json`,
different `inbox`, different `bot.pid`, and a different `.env`. The
chronotope channel's state at `~/.claude/channels/telegram/` is never
touched.

The token in `.env` here is a **different** Telegram bot from chronotope's.
Telegram only allows one polling consumer per token, so two bots sharing
one token would race for updates and lose messages — separate tokens are
required, not optional.
