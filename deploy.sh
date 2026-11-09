#!/usr/bin/env bash
set -euo pipefail

git add .
if ! git diff --cached --quiet; then
    git commit -m "Update viewport settings in index.html files"
fi
git push origin main