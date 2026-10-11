#!/usr/bin/env bash
# Demo of the full mission journey. Warning: step 1 deletes all data (mc-seed).
# Needs Postgres and the API running. Reads MC_API_URL, MC_CONFIG_DIR, DATABASE_URL, COLUMNS.
set -euo pipefail
cd "$(dirname "$0")/.."
export COLUMNS="${COLUMNS:-200}"
if [ -z "${MC_CONFIG_DIR:-}" ]; then
  MC_CONFIG_DIR=$(mktemp -d)
  trap 'rm -rf "$MC_CONFIG_DIR"' EXIT
  export MC_CONFIG_DIR
fi

OUT=""
heading() { printf '\n== %s ==\n' "$1"; }
# Print the command, run it, and keep its output in $OUT for the next steps.
mc() {
  local a shown=""
  for a in "$@"; do [[ $a == *" "* ]] && a="\"$a\""; shown+=" $a"; done
  printf '$ mc%s\n' "$shown"
  OUT=$(uv run mc "$@")
  printf '%s\n' "$OUT"
}
# Print the first table cell (the ID) of the row that has the given name.
row_id() { awk -F'│' -v n="$1" '$3 ~ n {gsub(/ /, "", $2); print $2}' <<<"$OUT"; }

heading "1. Reset the demo data"
echo '$ mc-seed'
uv run mc-seed

heading "2. Crew profile (ben)"
mc login --user ben
mc profile show
mc skills list
geology=$(row_id Geology)
mc profile skills set "$geology" --level 3
mc profile skills list
mc profile availability add --from 2027-06-01 --to 2027-06-03 --reason HOLIDAY
leave=$(awk '/^Added unavailability/ {print $3}' <<<"$OUT")
mc profile availability list
mc profile availability remove "$leave"
mc profile availability list

heading "3. Create the mission and its slots (leo)"
mc login --user leo
mc skills list
piloting=$(row_id Piloting)
medicine=$(row_id Medicine)
mc missions create --title "Demo Survey" --start 2027-03-01 --end 2027-03-10
mission=$(awk '/^Created mission/ {print $3}' <<<"$OUT")
mc missions slots add "$mission" --skill "$piloting" --level 3
mc missions slots add "$mission" --skill "$medicine" --level 3

heading "4. Matcher preview in DRAFT (leo)"
mc missions match "$mission"

heading "5. Submit (leo) and approve (diana)"
mc missions submit "$mission"
mc login --user diana
mc missions approve "$mission"

heading "6. Invite, accept and decline"
mc login --user leo
mc missions invite "$mission" --slot 1 --crew ben
mc missions invite "$mission" --slot 2 --crew hana
mc login --user ben
mc assignments accept "$mission"
mc login --user hana
mc assignments decline "$mission"
