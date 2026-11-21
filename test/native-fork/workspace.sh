#!/usr/bin/env bash
# Run from any directory. Components must be sibling checkouts of this repo.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
workspace="$root/go.work"
if [[ -e "$workspace" ]]; then
  echo "Refusing to overwrite existing $workspace" >&2
  exit 1
fi
cd "$root"
GOWORK=off go work init ./accelerator ./connector ./guest-runtime ./orchestrator ./sandboxer
# These pinned upstreams declare v0.2.0 component dependencies which are not
# published tags. Keep the module files intact and resolve them in this workspace.
for component in accelerator connector guest-runtime sandboxer; do
  GOWORK="$workspace" go work edit "-replace=github.com/kuasar-sandbox/$component@v0.2.0=./$component"
done
printf 'export GOWORK=%q\n' "$workspace"
