#!/usr/bin/env bash
# Synchronizes README.md, generates GitHub Actions Step Summary, and executes zero-bloat Git push
# using metrics/banner_telemetry.json as the single source of truth.

set -euo pipefail

TELEMETRY_FILE="metrics/banner_telemetry.json"
README_FILE="README.md"
BANNER_PATH="assets/profile-banner.webp"

if [[ ! -f "$TELEMETRY_FILE" ]]; then
  echo "Error: $TELEMETRY_FILE not found." >&2
  exit 1
fi

# 1. Extract metadata from telemetry JSON via jq
PAGE_URL=$(jq -r '.photo.page_url' "$TELEMETRY_FILE")
ALT_DESC=$(jq -r '.photo.alt_description | gsub("&"; "&amp;") | gsub("\""; "&quot;")' "$TELEMETRY_FILE")
AUTHOR_NAME=$(jq -r '.photo.author_name' "$TELEMETRY_FILE")
AUTHOR_URL=$(jq -r '.photo.author_url' "$TELEMETRY_FILE")
DOM_COLOR=$(jq -r '.photo.dominant_color' "$TELEMETRY_FILE")

DIM_PCT=$(jq -r '.placement.adaptive_dim_percent' "$TELEMETRY_FILE")
PRIMARY_CORNER=$(jq -r '.placement.primary_corner' "$TELEMETRY_FILE")
SECONDARY_CORNER=$(jq -r '.placement.secondary_corner // "MERGED"' "$TELEMETRY_FILE")
MERGED_ATTR=$(jq -r '.placement.merged_attribution' "$TELEMETRY_FILE")
WAKA_SCORES=$(jq -r '.placement.wakatime_box_luminance | to_entries | map("`\(.key): \(.value)`") | join(", ")' "$TELEMETRY_FILE")
ATTR_SCORES=$(jq -r '.placement.attribution_strip_luminance | to_entries | map("`\(.key): \(.value)`") | join(", ")' "$TELEMETRY_FILE")
WAKA_REASON=$(jq -r '.placement.wakatime_reasoning' "$TELEMETRY_FILE")
ATTR_REASON=$(jq -r '.placement.attribution_reasoning' "$TELEMETRY_FILE")

BANNER_KB=$(jq -r '.performance.banner_size_kb' "$TELEMETRY_FILE")
TOTAL_MS=$(jq -r '.performance.total_execution_ms' "$TELEMETRY_FILE")
API_MS=$(jq -r '.performance.unsplash_api_ms' "$TELEMETRY_FILE")
DL_MS=$(jq -r '.performance.image_download_ms' "$TELEMETRY_FILE")
RENDER_MS=$(jq -r '.performance.render_ms' "$TELEMETRY_FILE")

# 2. Synchronize README.md between UNSPLASH markers with cache-busting timestamp
VERSION_TAG=$(date +%s)
ASSET_URL="${BANNER_PATH}?v=${VERSION_TAG}"

awk -v url="$PAGE_URL" -v src="$ASSET_URL" -v alt="$ALT_DESC" '
  /<!-- UNSPLASH:START -->/ {
    print
    print "  <a href=\"" url "\">"
    print "    <img src=\"" src "\" alt=\"" alt "\" width=\"100%\" style=\"border-radius: 8px;\" />"
    print "  </a>"
    in_block = 1
    next
  }
  /<!-- UNSPLASH:END -->/ {
    in_block = 0
  }
  !in_block { print }
' "$README_FILE" > "${README_FILE}.tmp" && mv "${README_FILE}.tmp" "$README_FILE"

echo "Synchronized $README_FILE with cache-busted asset ($ASSET_URL)."

# 3. Publish Markdown Telemetry Table to GitHub Actions Step Summary (if running in CI)
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  cat <<EOF >> "$GITHUB_STEP_SUMMARY"
## Daily Profile Banner Telemetry

| Metric | Value |
| :--- | :--- |
| **Photographer** | [${AUTHOR_NAME}](${AUTHOR_URL}) ([Unsplash](${PAGE_URL})) |
| **Dominant Color / Dimming** | \`${DOM_COLOR}\` / \`${DIM_PCT}%\` |
| **WakaTime Corner** | \`${PRIMARY_CORNER}\` (${WAKA_SCORES}) |
| **Attribution Corner** | \`${SECONDARY_CORNER}\` (Merged: \`${MERGED_ATTR}\`, ${ATTR_SCORES}) |
| **Asset Size (2K WebP)** | \`${BANNER_KB} KB\` |
| **Execution Time** | \`${TOTAL_MS} ms\` (API: \`${API_MS} ms\`, DL: \`${DL_MS} ms\`, Render: \`${RENDER_MS} ms\`) |

### Algorithmic Placement Rationale
- **WakaTime Block:** ${WAKA_REASON}
- **Photo Attribution:** ${ATTR_REASON}
EOF
fi

# 4. Zero-Bloat Git Commit & Push (when --push flag is passed)
if [[ "${1:-}" == "--push" ]]; then
  git config --global user.name "github-actions[bot]"
  git config --global user.email "github-actions[bot]@users.noreply.github.com"
  git add README.md assets/ metrics/

  if ! git diff --staged --quiet; then
    LAST_AUTHOR=$(git log -1 --format='%an')
    if [[ "$LAST_AUTHOR" == "github-actions[bot]" ]]; then
      git commit --amend -m "chore(banner): update daily banner with fresh wakatime metrics"
      git push --force-with-lease
    else
      git commit -m "chore(banner): update daily banner with fresh wakatime metrics"
      git push
    fi
  else
    echo "No changes detected; skipping commit."
  fi
fi

