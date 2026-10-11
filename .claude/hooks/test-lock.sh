#!/usr/bin/env bash
# Test lock (D5). Usage: test-lock.sh close|open|status|check
# The lock is closed while .work/test-lock exists. The file holds the baseline of the test files.
set -u
. "$(dirname "$0")/lib.sh"
cd "$ROOT" || exit 1

# Prints "<path> TAB <blob hash>" for each test file. -w stores each blob, so check can print a restore command.
manifest() {
  local pat files
  pat=$(test_pattern) || return 1
  files=$(git ls-files -co --exclude-standard | grep -E -- "$pat" | sort -u |
    while IFS= read -r f; do [ -f "$f" ] && printf '%s\n' "$f"; done)
  [ -n "$files" ] || return 0
  paste <(printf '%s\n' "$files") <(printf '%s\n' "$files" | git hash-object -w --stdin-paths)
}

check() {
  [ -f "$LOCK" ] || return 0
  local now
  now=$(manifest) || return 1
  awk -F'\t' '
    FILENAME == ARGV[1] { old[$1] = $2; next }
    { new[$1] = $2 }
    END {
      for (f in old)
        if (!(f in new)) { printf "ERROR: %s was deleted while the test lock is closed. Restore it: git cat-file -p %s > \"%s\"\n", f, old[f], f; bad = 1 }
        else if (old[f] != new[f]) { printf "ERROR: %s changed while the test lock is closed. Restore it: git cat-file -p %s > \"%s\"\n", f, old[f], f; bad = 1 }
      for (f in new)
        if (!(f in old)) { printf "ERROR: %s was added while the test lock is closed. Delete it.\n", f; bad = 1 }
      exit bad
    }' "$LOCK" <(printf '%s' "$now")
}

case "${1:-}" in
  close)
    # Format the changed test files first. Else a later formatter run changes a locked file.
    if declare -F format >/dev/null; then
      pat=$(test_pattern) || exit 1
      { git diff --name-only HEAD; git ls-files -o --exclude-standard; } | grep -E -- "$pat" | sort -u |
        while IFS= read -r f; do [ -f "$f" ] && format "$f" >/dev/null 2>&1; done
    fi
    mkdir -p "$ROOT/.work"
    manifest > "$LOCK.tmp" || { rm -f "$LOCK.tmp"; exit 1; }
    mv "$LOCK.tmp" "$LOCK"
    echo "Test lock closed. Baseline: $(grep -c . "$LOCK") test files." ;;
  open) rm -f "$LOCK"; echo "Test lock open." ;;
  status) [ -f "$LOCK" ] && echo closed || echo open ;;
  check) check ;;
  *) echo "ERROR: Unknown command. Use: test-lock.sh close|open|status|check" >&2; exit 1 ;;
esac
