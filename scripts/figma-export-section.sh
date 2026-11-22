#!/usr/bin/env bash
# figma-export-section — export the node currently selected in Figma's Export panel.
#
#   ./scripts/figma-export-section <logical-x-of-export-button> <logical-y>
#
# Clicks the "Export <name>" button, waits for the save dialog, presses Save
# (the dialog remembers the `source` folder), and waits for the file to land.
set -euo pipefail
cd "$(dirname "$0")/.."

X="$1"; Y="$2"

./scripts/fgclick "$X" "$Y"

# wait for the native save dialog to appear (the export of a big section takes
# a while), then click "Save"
for i in $(seq 1 40); do
  sleep 3
  if osascript -e 'tell application "System Events" to tell process "Figma" to get name of every window' 2>/dev/null | grep -qi "save"; then
    break
  fi
done
sleep 2
./scripts/fgclick 1659 891
sleep 40

echo "--- exported ---"
ls -lat source/ | head -6
