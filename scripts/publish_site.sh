#!/usr/bin/env bash
# Publish the built site (site/ with site/data/) to GitHub Pages: one new commit on the gh-pages branch of
# baqata/unga-speech-analysis (docs/PLAN.md, section 5). Only the site's files are pushed, never the code.
#
# Usage: scripts/publish_site.sh [--noindex]
#
# It refuses a placeholder build (docs/data-contract.md, meta.build). With --noindex, the published copy asks
# search engines not to index it; the site looks the same either way.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="baqata/unga-speech-analysis"
BRANCH="gh-pages"
noindex=0
[[ "${1:-}" == "--noindex" ]] && noindex=1

[[ -f site/data/meta.json ]] || { echo "No site/data; run: uv run python -m pipeline.export site" >&2; exit 1; }
build=$(uv run python -c "import json; b = json.load(open('site/data/meta.json'))['build']; print('placeholder' if b['placeholder'] else b['date'] + ' ' + b['probabilities'][:12])")
[[ "$build" != "placeholder" ]] || { echo "A placeholder build is never published." >&2; exit 1; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
url="https://github.com/$REPO.git"
if git ls-remote --exit-code --heads "$url" "$BRANCH" >/dev/null 2>&1; then
  git clone --quiet --depth 1 --branch "$BRANCH" "$url" "$work/pages"
  git -C "$work/pages" rm -r --quiet --ignore-unmatch .
else
  git init --quiet -b "$BRANCH" "$work/pages"
  git -C "$work/pages" remote add origin "$url"
fi
cp -R site/. "$work/pages/"
touch "$work/pages/.nojekyll"   # serve the files as they are
if (( noindex )); then
  perl -pi -e 's|^<meta name="viewport"|<meta name="robots" content="noindex">\n<meta name="viewport"|' "$work/pages/index.html"
fi
find "$work/pages" -name .DS_Store -delete
git -C "$work/pages" add -A
git -C "$work/pages" commit --quiet -m "Publish site: build $build$( (( noindex )) && echo ' (noindex)')"
git -C "$work/pages" push --quiet origin "$BRANCH"
echo "Published build $build to https://github.com/$REPO/tree/$BRANCH"
