#!/usr/bin/env bash
# Refresh .claude/skills/fleet-gitops from fleetdm/fleet main (or a given ref).
# Usage: tools/update-gitops-skill.sh [git-ref]
set -euo pipefail
ref="${1:-main}"
root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$root/.claude/skills/fleet-gitops"
sha="$(curl -fsSL "https://api.github.com/repos/fleetdm/fleet/commits/$ref" | python3 -c 'import json,sys;print(json.load(sys.stdin)["sha"])')"
files="$(curl -fsSL "https://api.github.com/repos/fleetdm/fleet/git/trees/$sha?recursive=1" \
  | python3 -c 'import json,sys;[print(t["path"][len(".claude/skills/fleet-gitops/"):]) for t in json.load(sys.stdin)["tree"] if t["type"]=="blob" and t["path"].startswith(".claude/skills/fleet-gitops/")]')"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
for f in $files; do
  mkdir -p "$tmp/$(dirname "$f")"
  curl -fsSL "https://raw.githubusercontent.com/fleetdm/fleet/$sha/.claude/skills/fleet-gitops/$f" -o "$tmp/$f"
done
rm -rf "$dest" && mkdir -p "$dest" && cp -R "$tmp/." "$dest/"
echo "$sha" > "$dest/UPSTREAM_SHA"
echo "fleet-gitops skill updated to fleetdm/fleet@$sha. Review the diff in GitHub Desktop before committing."
