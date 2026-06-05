#!/bin/bash
# Double-click to pull your Instagram data and build the export. (macOS)
cd "$(dirname "$0")" || exit 1
echo "============================================"
echo "  Coach Current IG Kit — Export"
echo "============================================"
echo

if [ ! -d ".venv" ]; then
  echo "Run setup.command first."
  read -n 1 -s -r -p "Press any key to close..."; exit 1
fi
if [ ! -f ".env" ]; then
  echo "No .env found. Run setup.command, then add your credentials."
  read -n 1 -s -r -p "Press any key to close..."; exit 1
fi

./.venv/bin/python ig_export.py
STATUS=$?
echo
if [ $STATUS -eq 0 ]; then
  echo "Your export is in the 'export' folder."
  echo "Next: open this folder as a Cowork project and ask the"
  echo "social-analyst skill to analyze the export."
else
  echo "Something went wrong (see above). Most common fix: re-check .env."
fi
echo
read -n 1 -s -r -p "Press any key to close..."
echo
