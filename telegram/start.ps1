# Launch the spiral 3d Telegram bot pointed at this project's state dir.
# The plugin server respects TELEGRAM_STATE_DIR — same code, different state,
# fully insulated from ~/.claude/channels/telegram (chronotope).

$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
$plugin = "$env:USERPROFILE\.claude\plugins\cache\claude-plugins-official\telegram\0.0.6"

if (-not (Test-Path "$plugin\server.ts")) {
    Write-Error "telegram plugin not found at $plugin"
    exit 1
}

$env:TELEGRAM_STATE_DIR = $here
Write-Host "spiral telegram: state dir = $here"
Write-Host "spiral telegram: starting (Ctrl+C to stop)..."

# server.ts shuts down on stdin EOF (it's an MCP server expecting Claude Code
# to hold stdio open). Standalone, hand it an empty input stream that never
# closes so the bot poller stays alive.
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "bun"
$psi.Arguments = "`"$plugin\server.ts`""
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $false
$psi.RedirectStandardError = $false
$psi.UseShellExecute = $false
$proc = [System.Diagnostics.Process]::Start($psi)
# Don't write anything to stdin; just hold the handle open.
try {
    $proc.WaitForExit()
} finally {
    if (-not $proc.HasExited) { $proc.Kill() }
}
