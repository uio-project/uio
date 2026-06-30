#!/usr/bin/env bash
#
# project-sync.sh — reconcile GitHub project-management state from the declarative
# spec in .github/project.yml: org issue types, repository milestones, and the org
# Project board's custom fields.
#
# Idempotent and check-existence-first: it creates what is missing and patches
# drifted milestones; it never deletes. Re-running is a no-op once GitHub matches
# the spec.
#
# Usage:
#   scripts/project-sync.sh [--dry-run] [--spec PATH]
#
# Auth: needs a token with `admin:org` (issue types + project) and `repo`
# (milestones). In CI this is PROJECT_ADMIN_TOKEN; locally, `gh auth login`.
# The built-in GITHUB_TOKEN cannot write org-level objects.
#
# NOT handled (no GitHub API): board VIEWS and the AUTO-ADD workflow — see
# docs/runbooks/github-project-setup.md.

set -euo pipefail

DRY_RUN=0
SPEC_FILE=".github/project.yml"
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --spec) SPEC_FILE="$2"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

# --- Token guard: a missing secret is a clean skip, not a failed run. ---
TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
if [ -z "$TOKEN" ] && ! gh auth status >/dev/null 2>&1; then
  echo "::warning::No token (PROJECT_ADMIN_TOKEN/GH_TOKEN) and no gh login; skipping project sync."
  exit 0
fi

for bin in gh jq python3; do
  command -v "$bin" >/dev/null 2>&1 || { echo "error: '$bin' is required" >&2; exit 1; }
done

run() {  # run <description> <gh args...>
  local desc="$1"; shift
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "DRY-RUN would: $desc"
  else
    echo "==> $desc"
    "$@"
  fi
}

# Parse YAML → JSON once (PyYAML; install via pip in CI).
SPEC="$(python3 -c 'import yaml,json,sys; json.dump(yaml.safe_load(open(sys.argv[1])), sys.stdout, default=str)' "$SPEC_FILE")"
q() { jq -r "$1" <<<"$SPEC"; }

OWNER="$(q '.owner')"
REPO="$(q '.repo')"
echo "Reconciling $OWNER/$REPO from $SPEC_FILE (dry-run=$DRY_RUN)"

# ---------------------------------------------------------------------------
# 1. Org issue types
# ---------------------------------------------------------------------------
echo "--- Issue types ---"
existing_types="$(gh api "orgs/$OWNER/issue-types" --jq '.[].name' 2>/dev/null || true)"
while IFS=$'\t' read -r name desc color; do
  [ -z "$name" ] && continue
  if grep -Fxq "$name" <<<"$existing_types"; then
    echo "ok: issue type '$name' exists"
  else
    run "create issue type '$name'" \
      gh api -X POST "orgs/$OWNER/issue-types" \
        -f "name=$name" -f "description=$desc" -f "color=$color" -F is_enabled=true
  fi
done < <(q '.issue_types[] | [.name, .description, .color] | @tsv')

# ---------------------------------------------------------------------------
# 2. Repository milestones
# ---------------------------------------------------------------------------
echo "--- Milestones ---"
milestones_json="$(gh api "repos/$OWNER/$REPO/milestones?state=all&per_page=100")"
while IFS=$'\t' read -r title state due desc; do
  [ -z "$title" ] && continue
  due_iso=""
  [ "$due" != "null" ] && [ -n "$due" ] && due_iso="${due}T00:00:00Z"
  number="$(jq -r --arg t "$title" '.[] | select(.title==$t) | .number' <<<"$milestones_json")"
  args=(-f "title=$title" -f "state=$state" -f "description=$desc")
  [ -n "$due_iso" ] && args+=(-f "due_on=$due_iso")
  if [ -n "$number" ]; then
    # Only patch on drift so re-runs are true no-ops.
    cur="$(jq -c --arg t "$title" '.[] | select(.title==$t) | {state, description, due_on}' <<<"$milestones_json")"
    cur_state="$(jq -r '.state' <<<"$cur")"
    cur_desc="$(jq -r '.description // ""' <<<"$cur")"
    cur_due="$(jq -r '.due_on // ""' <<<"$cur")"
    if [ "$cur_state" = "$state" ] && [ "$cur_desc" = "$desc" ] && [ "$cur_due" = "$due_iso" ]; then
      echo "ok: milestone '$title' (#$number) up to date"
      continue
    fi
    run "patch milestone '$title' (#$number → state=$state)" \
      gh api -X PATCH "repos/$OWNER/$REPO/milestones/$number" "${args[@]}"
  else
    run "create milestone '$title' (state=$state)" \
      gh api -X POST "repos/$OWNER/$REPO/milestones" "${args[@]}"
  fi
done < <(q '.milestones[] | [.title, .state, (.due_on // "null"), (.description // "")] | @tsv')

# ---------------------------------------------------------------------------
# 3. Project board custom fields
# ---------------------------------------------------------------------------
echo "--- Project board fields ---"
PROJECT_NUMBER="$(q '.project.number')"
project_data="$(gh api graphql -f query='
  query($o:String!, $n:Int!) {
    organization(login:$o) {
      projectV2(number:$n) {
        id
        fields(first:50) { nodes { ... on ProjectV2FieldCommon { name } } }
      }
    }
  }' -f o="$OWNER" -F n="$PROJECT_NUMBER")"
PROJECT_ID="$(jq -r '.data.organization.projectV2.id' <<<"$project_data")"
existing_fields="$(jq -r '.data.organization.projectV2.fields.nodes[].name' <<<"$project_data")"

color_for() {  # round-robin a palette for single-select options
  local palette=(BLUE GREEN YELLOW ORANGE RED PURPLE PINK GRAY)
  echo "${palette[$(( $1 % ${#palette[@]} ))]}"
}

create_field() {  # create_field <name> <SINGLE_SELECT|DATE|NUMBER|TEXT> [opt...]
  local name="$1" dtype="$2"; shift 2
  local opts_literal="" i=0
  if [ "$dtype" = "SINGLE_SELECT" ]; then
    for opt in "$@"; do
      [ -n "$opts_literal" ] && opts_literal+=","
      opts_literal+="{name:\"$opt\",color:$(color_for "$i"),description:\"\"}"
      i=$((i+1))
    done
    opts_literal=",singleSelectOptions:[$opts_literal]"
  fi
  local mutation="mutation{createProjectV2Field(input:{projectId:\"$PROJECT_ID\",dataType:$dtype,name:\"$name\"$opts_literal}){projectV2Field{... on ProjectV2FieldCommon{id name}}}}"
  run "create board field '$name' ($dtype)" gh api graphql -f query="$mutation"
}

field_count="$(q '.project.fields | length')"
for idx in $(seq 0 $((field_count - 1))); do
  fname="$(q ".project.fields[$idx].name")"
  ftype="$(q ".project.fields[$idx].type")"
  if grep -Fxq "$fname" <<<"$existing_fields"; then
    echo "ok: board field '$fname' exists"
    continue
  fi
  case "$ftype" in
    single_select)
      mapfile -t opts < <(q ".project.fields[$idx].options[]")
      create_field "$fname" SINGLE_SELECT "${opts[@]}" ;;
    date)   create_field "$fname" DATE ;;
    number) create_field "$fname" NUMBER ;;
    text)   create_field "$fname" TEXT ;;
    *) echo "warning: unknown field type '$ftype' for '$fname'; skipping" >&2 ;;
  esac
done

echo "Project sync complete."
