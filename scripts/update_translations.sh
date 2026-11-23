#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src/writing_tools"
LOCALES_DIR="$SRC_DIR/resources/locales"
POT_DIR="$ROOT_DIR/pot_files"

mkdir -p "$POT_DIR"

# Generate .pot files from all Python modules
xgettext --language=Python --keyword=_ "$SRC_DIR/app.py" -o "$POT_DIR/app.pot"
for file in "$SRC_DIR"/ui/*.py; do
  base="$(basename "$file" .py)"
  if [[ "$base" == "__init__" ]]; then
    continue
  fi
  xgettext --language=Python --keyword=_ "$file" -o "$POT_DIR/${base}.pot"
done

# Merge into a single .pot file
msgcat "$POT_DIR"/*.pot -o "$POT_DIR/merged.pot"

# Update and compile .po files
for locale in "$LOCALES_DIR"/*; do
  [[ -d "$locale" ]] || continue
  echo -n "Updating $locale translation files... "
  msgmerge --update "$locale/LC_MESSAGES/messages.po" "$POT_DIR/merged.pot"
  msgfmt -o "$locale/LC_MESSAGES/messages.mo" "$locale/LC_MESSAGES/messages.po"
  echo "done."
done
