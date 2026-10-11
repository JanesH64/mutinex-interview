#!/usr/bin/env bash
# Claude Code hooks for the kit. settings.json calls: hook.sh stop|pre-tool|post-tool
# Exit 2 sends stderr to Claude: Stop continues the turn, PreToolUse denies the tool.
set -u
. "$(dirname "$0")/lib.sh"
MAX_FIX_ATTEMPTS=3

input=$(cat)
field() { jq -r "$1 // empty" <<<"$input"; }
agent=$(field .agent_id) # Present only when the hook fires inside a subagent.

# Prints the edited file path relative to the repo root. Prints nothing for a file outside the project.
relpath() {
  local f d rel
  f=$(field '.tool_input.file_path // .tool_input.notebook_path')
  [ -n "$f" ] || return
  # Resolve symlinked folders, for example /tmp and /private/tmp. Write can name a folder that does not exist yet.
  d=$(dirname "$f")
  while [ ! -d "$d" ]; do d=$(dirname "$d"); done
  rel=$(cd "$d" && pwd -P)/${f#"$d"/}
  rel=${rel#"$ROOT"/}
  case "$rel" in /*) return ;; esac
  printf '%s\n' "$rel"
}

case "${1:-}" in
stop)
  [ -n "$agent" ] && exit 0
  attempts="$ROOT/.work/stop-attempts"
  # While the lock is closed, red tests are expected. Check only the lock.
  check=("$DIR/verify.sh" fast) name=verify:fast
  [ -f "$LOCK" ] && check=("$DIR/test-lock.sh" check) name="The test lock check"
  if out=$("${check[@]}" 2>&1); then rm -f "$attempts"; exit 0; fi
  # Loop guard: stop_hook_active is true while Claude continues because of this hook.
  count=0
  [ "$(field .stop_hook_active)" = true ] && count=$(cat "$attempts" 2>/dev/null || echo 0)
  count=$((count + 1))
  if [ "$count" -gt "$MAX_FIX_ATTEMPTS" ]; then
    rm -f "$attempts"
    jq -n --arg m "$name still fails after $MAX_FIX_ATTEMPTS fix attempts. Read the failures and decide the next step." '{systemMessage: $m}'
    exit 0
  fi
  mkdir -p "$ROOT/.work" && echo "$count" > "$attempts"
  echo "ERROR: $name failed. Fix the failures below, then stop again. If a test fails on purpose (a red test or a bug reproduction), do not change code. Report the failing test and stop." >&2
  echo "$out" >&2
  exit 2 ;;

pre-tool)
  if [ "$(field .tool_name)" = Bash ]; then
    cmd=$(field .tool_input.command)
    # text match only. An indirect command (rm -r .work, a name built at run time) passes. The reviewer and the PR review are the backstop.
    # Reads of test-lock.sh and "status" pass.
    if [ -n "$agent" ] && [[ $cmd =~ test-lock\.sh[[:space:]]+(open|close)|\.work/test-lock ]]; then
      echo "ERROR: A subagent cannot change the test lock. Report the problem to the main session and stop." >&2
      exit 2
    fi
    exit 0
  fi
  rel=$(relpath)
  [ -n "$rel" ] || exit 0
  if [[ $rel == .work/test-lock* ]]; then
    echo "ERROR: Do not edit the test lock state. Use .claude/hooks/test-lock.sh." >&2
    exit 2
  fi
  if [ -f "$LOCK" ]; then
    pat=$(test_pattern) || exit 2
    if grep -qE -- "$pat" <<<"$rel"; then
      echo "ERROR: The test lock is closed. Do not edit $rel. Change the production code. If the test is wrong, report it and stop. The lock owner opens the lock." >&2
      exit 2
    fi
  fi
  exit 0 ;;

post-tool)
  # Format only. verify:fast reports format and lint errors, so a failure here stays silent.
  # format() in .claude/project.sh gets the repo-relative path as $1.
  declare -F format >/dev/null || exit 0
  rel=$(relpath)
  [ -n "$rel" ] && [ -f "$ROOT/$rel" ] && (cd "$ROOT" && format "$rel") >/dev/null 2>&1
  exit 0 ;;

*) echo "ERROR: Unknown hook. Use: hook.sh stop|pre-tool|post-tool" >&2; exit 1 ;;
esac
