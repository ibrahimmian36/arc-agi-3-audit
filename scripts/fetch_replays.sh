#!/usr/bin/env bash
# Fetch the Foundation's human replay archive into a directory OUTSIDE the
# repository, verify it is a zip, record its hash, and list it WITHOUT
# extracting. Run only with the lead author's explicit go-ahead; nothing here
# runs automatically, and nothing from the archive is ever committed.
#
#   bash scripts/fetch_replays.sh <google-drive-file-id-or-share-url>
#
# The Drive folder behind the announcement's link holds
# arc_agi_3_public_demo_human_testing.zip (106 MB). Drive's "confirm" step for
# large files is handled by following its redirect with a cookie jar.
set -euo pipefail
DEST="${REPLAYS_DIR:-$HOME/Desktop/3kvc/replays_data}"
mkdir -p "$DEST"
ID="${1:?file id or share url}"
ID="$(echo "$ID" | sed -E 's#.*/d/([^/]+).*#\1#; s#.*id=([^&]+).*#\1#')"
OUT="$DEST/arc_agi_3_public_demo_human_testing.zip"
JAR="$(mktemp)"
echo "fetching Drive file $ID -> $OUT"
curl -sL -c "$JAR" "https://drive.google.com/uc?export=download&id=$ID" -o "$OUT.part"
if file "$OUT.part" | grep -qi html; then
  TOKEN="$(grep -oE 'confirm=[0-9A-Za-z_-]+' "$OUT.part" | head -1 | cut -d= -f2 || true)"
  UUID="$(grep -oE 'name="uuid" value="[^"]+"' "$OUT.part" | head -1 | sed -E 's/.*value="([^"]+)"/\1/' || true)"
  curl -sL -b "$JAR" "https://drive.usercontent.google.com/download?id=$ID&export=download&confirm=${TOKEN:-t}${UUID:+&uuid=$UUID}" -o "$OUT.part"
fi
rm -f "$JAR"
file "$OUT.part" | grep -qi "zip" || { echo "not a zip archive; not kept" >&2; rm -f "$OUT.part"; exit 1; }
mv "$OUT.part" "$OUT"
echo "bytes: $(wc -c < "$OUT" | tr -d ' ')"
echo "sha256: $(shasum -a 256 "$OUT" | cut -d' ' -f1)"
echo "--- listing (not extracting) ---"
unzip -l "$OUT" | tail -1
unzip -l "$OUT" | awk 'NR>3 && $4 ~ /\.recording\.jsonl$/ {n++; s+=$1} END {print "recordings: " n ", uncompressed bytes: " s}'
