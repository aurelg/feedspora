#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

function execute_tests() {
  TESTDIR="${1:-}"
  for CONFIG in "${TESTDIR}"/*.yml; do
    BASEFILENAME=$(basename -s .yml -- "$CONFIG")
    echo "    $BASEFILENAME..."
    rm -f "$TESTDIR"/"$BASEFILENAME".{out,log,db}
    (
      cd "$TESTDIR" &&
        python -m feedspora --testing "$BASEFILENAME" \
          >"$BASEFILENAME".out \
          2>"$BASEFILENAME".log
    )
    grep 'ERROR:' "$TESTDIR"/"$BASEFILENAME".log || true
  done
}

case "${1:-}" in
all)
  echo "Executing all tests"
  execute_tests "test_feed"
  execute_tests "test_post"
  ;;
feed)
  execute_tests "test_feed"
  ;;
post)
  execute_tests "test_post"
  ;;
*)
  echo "No Unknown test specification '${1:-}' - aborting"
  echo "${0:-} all | feed | post"
  exit 1
  ;;
esac

echo "All specified tests executed"
