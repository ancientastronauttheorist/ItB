#!/bin/bash
# Install git hooks from scripts/hooks/ into .git/hooks/.
# Run once per checkout. Idempotent.

set -e

cd "$(dirname "$0")/.."
REPO=$(pwd)

HOOK_SRC="$REPO/scripts/hooks"
HOOK_DST="$REPO/.git/hooks"

if [ ! -d "$HOOK_DST" ]; then
    echo "Error: $HOOK_DST does not exist. Is this a git checkout?"
    exit 1
fi

mkdir -p "$HOOK_DST"

for hook in "$HOOK_SRC"/*; do
    name=$(basename "$hook")
    dst="$HOOK_DST/$name"
    if [ -L "$dst" ] || [ -f "$dst" ]; then
        rm "$dst"
    fi
    ln -s "$hook" "$dst"
    chmod +x "$hook"
    echo "Installed $name -> $dst"
done

echo ""
echo "Done. Hooks will now run on git commit."
