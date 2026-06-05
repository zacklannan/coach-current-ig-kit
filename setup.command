#!/bin/bash
# Double-click once to set up. (macOS)
cd "$(dirname "$0")" || exit 1
echo "============================================"
echo "  Coach Current IG Kit — Setup"
echo "============================================"
echo

if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else
  echo "Python 3 isn't installed. Get it at https://www.python.org/downloads/ then run this again."
  read -n 1 -s -r -p "Press any key to close..."; exit 1
fi
echo "Using: $($PY --version)"

[ -d ".venv" ] || { echo "Creating environment..."; $PY -m venv .venv; }
echo "Installing packages..."
./.venv/bin/pip install --upgrade pip >/dev/null 2>&1
./.venv/bin/pip install -r requirements.txt || { echo "Install failed."; read -n 1 -s -r -p "Press any key..."; exit 1; }

[ -f ".env" ] || cp .env.example .env

# Capture (or update) credentials right here, so nobody has to find/edit a hidden file.
# Re-run this any time to update them (e.g. when your token expires or you add a permission).
echo
echo "--------------------------------------------"
echo "  Enter your Instagram credentials"
echo "  (from your Meta app — see the SOP)."
echo "  Leave a line BLANK to keep what's already"
echo "  saved. This is also how you UPDATE them."
echo "--------------------------------------------"
printf "Instagram App Secret: "
read -r SECRET
printf "Token: "
read -r TOKEN

if [ -n "$SECRET" ] || [ -n "$TOKEN" ]; then
  ./.venv/bin/python save_creds.py "$SECRET" "$TOKEN"
  echo
  echo "Done. Now double-click run.command."
else
  echo
  echo "No changes. (Run setup.command again any time to update your"
  echo "credentials, or edit the .env file directly.)"
fi
echo
read -n 1 -s -r -p "Press any key to close..."
echo
