#!/usr/bin/env bash
# Pushes this folder to GitHub, replacing whatever is currently in the repo.
#
#   bash push_to_github.sh
#
# Safe to re-run. Checks the things that usually go wrong before touching anything.

set -euo pipefail

REPO_URL="https://github.com/shashankagrawal24/indiafd.git"
REPO_WEB="https://github.com/shashankagrawal24/indiafd"

red()  { printf '\033[31m%s\033[0m\n' "$1"; }
grn()  { printf '\033[32m%s\033[0m\n' "$1"; }
say()  { printf '\n%s\n' "$1"; }

# --- 1. are we in the right folder? -----------------------------------------
if [ ! -f "pyproject.toml" ] || [ ! -d "src/fdrates" ]; then
  red "This does not look like the india-fd-rates folder."
  echo "cd into the unzipped folder first, then run this script again."
  echo "You should see pyproject.toml and a src/ folder when you run: ls"
  exit 1
fi

# --- 2. did the hidden .github folder survive the unzip? ---------------------
if [ ! -f ".github/workflows/weekly.yml" ]; then
  red "MISSING: .github/workflows/weekly.yml"
  echo
  echo "The hidden .github folder was lost when the zip was extracted."
  echo "Without it there is no weekly schedule and nothing will ever run."
  echo
  echo "Unzip the archive again from the command line, which keeps hidden files:"
  echo "    unzip -o india-fd-rates.zip"
  exit 1
fi

# --- 3. is git available? ----------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  red "git is not installed."
  echo "macOS:   xcode-select --install"
  echo "Windows: install from https://git-scm.com"
  exit 1
fi

# --- 4. warn before overwriting ----------------------------------------------
say "About to replace everything in $REPO_WEB with this folder."
echo "This removes the uploaded zip and the sample fd_rates.csv from the repo root."
printf 'Continue? [y/N] '
read -r answer
case "$answer" in
  [yY]*) ;;
  *) echo "Cancelled. Nothing was changed."; exit 0 ;;
esac

# --- 5. push -----------------------------------------------------------------
[ -d .git ] || git init -b main

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REPO_URL"
else
  git remote add origin "$REPO_URL"
fi

git add -A
git commit -m "init: weekly Indian bank FD rate collector" || echo "(nothing new to commit)"

say "Pushing. If a browser window opens, sign in to GitHub there."
if ! git push -u origin main --force; then
  red "Push failed."
  echo
  echo "Almost always an authentication problem. Fix it with the GitHub CLI:"
  echo "    gh auth login          # choose GitHub.com, HTTPS, login with a web browser"
  echo "then run this script again. Install gh with 'brew install gh' (macOS)"
  echo "or 'winget install GitHub.cli' (Windows)."
  exit 1
fi

grn "Pushed."
cat <<EOF

Two things left, both in the browser:

1. $REPO_WEB/settings/actions
   Under "Workflow permissions" pick "Read and write permissions", then Save.
   Without this the weekly job cannot commit the CSV back.

2. $REPO_WEB/actions
   Click "Weekly FD rates" -> "Run workflow" -> Run.
   Takes 10-20 minutes. Open the run's Summary when it finishes.

EOF
