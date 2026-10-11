#!/usr/bin/env bash
# verify:fast and verify:full (D4). Usage: verify.sh fast|full
set -u
. "$(dirname "$0")/lib.sh"

case "${1:-}" in
  fast) cmd=$(cfg VERIFY_FAST) || exit 1 ;;
  full) cmd=$(cfg VERIFY_FULL) || exit 1 ;;
  *) echo "ERROR: Unknown tier. Use: verify.sh fast|full" >&2; exit 1 ;;
esac
cd "$ROOT" || exit 1

# The PreToolUse hook does not see test changes that Bash makes. The baseline check finds them.
# A lock failure does not stop the checks, so the caller sees every result.
"$DIR/test-lock.sh" check
lock=$?
bash -c "$cmd" || exit
exit "$lock"
