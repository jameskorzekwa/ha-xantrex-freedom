#!/usr/bin/env bash

set -euo pipefail

rm -f xantrex_freedom.zip

(
  cd custom_components/xantrex_freedom
  zip -r ../../xantrex_freedom.zip . -x '*__pycache__*' '*.pyc'
)

archive_contents="$(unzip -Z1 xantrex_freedom.zip)"
grep -qx "manifest.json" <<<"${archive_contents}"

if grep -q '^xantrex_freedom/' <<<"${archive_contents}"; then
  echo "Release archive must contain integration files at its root." >&2
  exit 1
fi
