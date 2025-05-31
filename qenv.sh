#!/bin/bash
# qenv.sh - Generate .env file for TgMusicBot
# Copyright (c) 2025 AshokShau
# Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html

# Note: This script creates a .env file in the repository's root folder for the TgMusicBot project.
# The .env file is used by src/config.py.
# Run this script from anywhere in the repository: ./qenv.sh

# Ensure the script has executable permissions
chmod +x "$0"

# Find the repository root directory
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ]; then
    echo "Error: Not inside a git repository. Please run this script from within the TgMusicBot repository."
    exit 1
fi

ENV_FILE="$REPO_ROOT/.env"

# Remove existing .env file if it exists
[ -f "$ENV_FILE" ] && rm "$ENV_FILE"

# Write environment variables to .env file
cat << EOF > "$ENV_FILE"
# Telegram API credentials
API_ID=24620300
API_HASH=9a098f01aa56c836f2e34aee4b7ef963
TOKEN=

# Bot configuration
MIN_MEMBER_COUNT=10
OWNER_ID=5960968099
LOGGER_ID=-1002030443562

# Session strings you could add more than one string sessions (STRING1 to STRING10)
# Format like STRING2= and So On For Upto 10 Sessions For Assistant
STRING1=

# MongoDB and API settings
MONGO_URI=
API_URL=
API_KEY=

# Proxy settings
PROXY=

# Bot behavior
DEFAULT_SERVICE=youtube
DOWNLOADS_DIR=database/music
SUPPORT_GROUP=https://t.me/BillaCore
SUPPORT_CHANNEL=https://t.me/BillaSpace
IGNORE_BACKGROUND_UPDATES=True
AUTO_LEAVE=False

# Cookie URLs (space or comma-separated list of URLs)
COOKIES_URL=

# Developer IDs (space-separated list of Telegram user IDs)
DEVS=5960968099
EOF

echo "Generated $ENV_FILE in the repository's root folder for use with src/config.py."
