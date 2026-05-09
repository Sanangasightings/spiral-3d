@echo off
REM Launch Claude Code in this project, connected to the spiral telegram channel.
REM
REM Two things have to happen before we hand off to claude:
REM   1. Stop any standalone spiral bot (start.sh / start.ps1) that's still
REM      polling the token. Telegram allows only one polling consumer per
REM      token, and the plugin's server.ts that claude is about to spawn
REM      would 409 forever.
REM   2. Point TELEGRAM_STATE_DIR at this project's telegram dir so the
REM      plugin runs against this channel's access.json/inbox/approved,
REM      not chronotope's at ~/.claude/channels/telegram/.

set "TELEGRAM_STATE_DIR=%~dp0telegram"

if exist "%TELEGRAM_STATE_DIR%\bot.pid" (
  for /f %%p in ('type "%TELEGRAM_STATE_DIR%\bot.pid"') do (
    echo Stopping standalone spiral bot pid=%%p ...
    taskkill /PID %%p /F >nul 2>&1
  )
  del "%TELEGRAM_STATE_DIR%\bot.pid" >nul 2>&1
)

claude --channels plugin:telegram@claude-plugins-official --dangerously-skip-permissions
