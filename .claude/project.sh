# Project values for the kit hooks. Copy to .claude/project.sh. The hooks source it. Do not run it.
# Give one line for each area, with a comment that names the area and its tool.

# Test files: extended regexes on repo-relative paths. The test lock blocks edits to each match.
# Include test setup and e2e files. If the agent can change them, a test can pass without a fix.
TEST_PATTERNS=(
  '^packages/[^/]+/tests/'   # all packages: pytest
)

# Formats one file after each edit. $1 is the repo-relative path. It runs at the repo root.
# Delete this function if the project has no formatter.
format() {
  case "$1" in
    *.py) uv run ruff format -q "$1" && uv run ruff check --fix -q "$1" ;;
  esac
}
