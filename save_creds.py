#!/usr/bin/env python3
"""Write Instagram credentials into .env. Used by setup.command (Mac) and
setup.bat (Windows). Blank args are ignored (keeps the existing value).
A new token clears the saved long-lived token so it actually takes effect."""
import sys
from dotenv import set_key

secret = sys.argv[1] if len(sys.argv) > 1 else ""
token = sys.argv[2] if len(sys.argv) > 2 else ""

if secret:
    set_key(".env", "IG_APP_SECRET", secret)
if token:
    set_key(".env", "IG_SHORT_LIVED_TOKEN", token)
    set_key(".env", "IG_ACCESS_TOKEN", "")  # so the new token is used, not the old saved one
print(">>> Saved to your .env file.")
