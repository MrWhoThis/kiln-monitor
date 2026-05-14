#!/usr/bin/env bash
set -euo pipefail

# Release script for kiln-monitor (HACS custom integration).
#
# Bumps manifest.json version, commits, tags YYYY.M.D, moves the `latest`
# tag, and pushes everything to origin.
#
# Usage:
#   scripts/release.sh                    # version = today (auto-suffix if taken)
#   scripts/release.sh -v 2026.5.13.1     # explicit version
#   scripts/release.sh -m "Fix options flow on HA 2025.12+"
#   scripts/release.sh -n                 # dry run

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

MANIFEST="custom_components/kiln_monitor/manifest.json"
BRANCH="main"
REMOTE="origin"

VERSION=""
MESSAGE=""
DRY_RUN=0

usage() {
  sed -n '4,13p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--version) VERSION="$2"; shift 2 ;;
    -m|--message) MESSAGE="$2"; shift 2 ;;
    -n|--dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "unknown arg: $1" >&2; usage 1 ;;
  esac
done

run() {
  if (( DRY_RUN )); then
    echo "DRY  $*"
  else
    echo "RUN  $*"
    "$@"
  fi
}

# --- preflight -------------------------------------------------------------

[[ -f "$MANIFEST" ]] || { echo "manifest not found: $MANIFEST" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$BRANCH" ]]; then
  echo "must be on $BRANCH (currently on $current_branch)" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "working tree is dirty — commit or stash first:" >&2
  git status --short >&2
  exit 1
fi

git fetch --quiet "$REMOTE" "$BRANCH"
local_sha="$(git rev-parse HEAD)"
remote_sha="$(git rev-parse "$REMOTE/$BRANCH")"
if [[ "$local_sha" != "$remote_sha" ]]; then
  echo "local $BRANCH is not in sync with $REMOTE/$BRANCH — pull/push first" >&2
  exit 1
fi

# --- compute version -------------------------------------------------------

today="$(date +%Y).$(date +%-m).$(date +%-d)"

if [[ -z "$VERSION" ]]; then
  VERSION="$today"
  if git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
    n=1
    while git rev-parse -q --verify "refs/tags/${today}.${n}" >/dev/null; do
      n=$((n + 1))
    done
    VERSION="${today}.${n}"
  fi
fi

if git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
  echo "tag $VERSION already exists" >&2
  exit 1
fi

current_version="$(jq -r .version "$MANIFEST")"
COMMIT_MSG="${MESSAGE:-Release $VERSION}"

# --- plan + confirm --------------------------------------------------------

cat <<EOF

Release plan
  current version : $current_version
  new version     : $VERSION
  commit message  : $COMMIT_MSG
  branch          : $BRANCH
  remote          : $REMOTE
  dry run         : $DRY_RUN

EOF

if (( ! DRY_RUN )); then
  read -r -p "Proceed? [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]] || { echo "aborted"; exit 1; }
fi

# --- execute ---------------------------------------------------------------

tmp="$(mktemp)"
jq --arg v "$VERSION" '.version = $v' "$MANIFEST" > "$tmp"
if (( DRY_RUN )); then
  echo "DRY  would write new manifest:"
  diff -u "$MANIFEST" "$tmp" || true
  rm -f "$tmp"
else
  mv "$tmp" "$MANIFEST"
fi

run git add "$MANIFEST"
run git commit -m "$COMMIT_MSG"
run git tag -a "$VERSION" -m "$VERSION"
run git tag -f latest
run git push "$REMOTE" "$BRANCH"
run git push "$REMOTE" "$VERSION"
run git push -f "$REMOTE" latest

cat <<EOF

Released $VERSION.

Next: draft GitHub release notes at
  https://github.com/igorparsadanov/kiln-monitor/releases/new?tag=$VERSION
EOF
