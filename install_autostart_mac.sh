#!/usr/bin/env bash
# Starts the auto-trader stack every weekday at 09:00 (Mac must be on and logged in), so the 09:20 FII open trade
# and the opening-range data are never missed. Run once:  ./install_autostart_mac.sh     Remove: ./install_autostart_mac.sh --remove
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.autotrader.up"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
if [[ "${1:-}" == "--remove" ]]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"; echo "Autostart removed."; exit 0
fi
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/logs"
{
  echo '<?xml version="1.0" encoding="UTF-8"?>'
  echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
  echo '<plist version="1.0"><dict>'
  echo "  <key>Label</key><string>$LABEL</string>"
  echo "  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$ROOT/up.sh</string></array>"
  echo "  <key>WorkingDirectory</key><string>$ROOT</string>"
  echo '  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Applications/Docker.app/Contents/Resources/bin</string></dict>'
  echo '  <key>StartCalendarInterval</key><array>'
  for d in 1 2 3 4 5; do echo "    <dict><key>Weekday</key><integer>$d</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>"; done
  echo '  </array>'
  echo "  <key>StandardOutPath</key><string>$ROOT/logs/autostart.log</string>"
  echo "  <key>StandardErrorPath</key><string>$ROOT/logs/autostart.log</string>"
  echo '</dict></plist>'
} > "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Autostart installed: up.sh runs Mon-Fri 09:00 (log: $ROOT/logs/autostart.log)."
