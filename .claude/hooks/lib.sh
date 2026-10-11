# Shared setup for the kit scripts. Source this file. Do not run it.
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(git -C "$DIR" rev-parse --show-toplevel) || exit 1
LOCK="$ROOT/.work/test-lock"

# Project values: TEST_PATTERNS and format(). The project owns this file.
[ -f "$ROOT/.claude/project.sh" ] && . "$ROOT/.claude/project.sh"

# Prints the project value $1. The settings env reaches hooks and Bash. A terminal run reads settings.json.
cfg() {
  local v="${!1:-}"
  [ -n "$v" ] || v=$(jq -r --arg k "$1" '.env[$k] // empty' "$ROOT/.claude/settings.json" 2>/dev/null)
  case "$v" in
    '' | '<'*) echo "ERROR: $1 is not set. Set it in the env block of .claude/settings.json." >&2; return 1 ;;
  esac
  printf '%s\n' "$v"
}

# Prints TEST_PATTERNS as one extended regex. Bash 3.2 treats an empty array as unset.
test_pattern() {
  [ -n "${TEST_PATTERNS+x}" ] || { echo "ERROR: TEST_PATTERNS is not set. Set it in .claude/project.sh." >&2; return 1; }
  local IFS='|'
  printf '%s\n' "${TEST_PATTERNS[*]}"
}
