#!/usr/bin/env bash
# Checks for the verify tiers (D4). Usage: check.sh fast|full
# Prints only failures, each line marked ERROR. Exits non-zero if a check fails.
set -u
cd "$(dirname "$0")/.." || exit 1
failed=0

# Runs one check: run <name> '<command>'. On failure, prints the last 40 lines (a build log can have hundreds).
# Give one command for each call. A chain prints the success output of the earlier commands when a later one fails.
run() {
  local name=$1 out
  shift
  out=$(bash -c "$*" 2>&1) || { tail -n 40 <<<"$out" | sed "s/^/ERROR: $name: /"; failed=1; }
}

# Format check, lint, typecheck and unit tests. Example: run api-lint 'cd api && uv run ruff check .'
fast() {
  run format 'uv run ruff format --check -q .'
  run lint 'uv run ruff check -q .'
  run tests 'uv run pytest -q -m "not e2e"'
}

# Build, all other tests and e2e. Give each e2e step its own call: start, smoke, browser tests, stop.
full() {
  run e2e 'uv run pytest -q -m e2e'
}

case "${1:-}" in
  fast) fast ;;
  full) fast; full ;;
  *) echo "ERROR: Unknown tier. Use: check.sh fast|full" >&2; exit 1 ;;
esac
exit "$failed"
