#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

PASSORFAIL=0
function execute_tests() {
  TESTDIR="${1:-}"
  for CONFIG in "${TESTDIR}"/*.yml; do
    BASEFILENAME=$(basename -s .yml -- "$CONFIG")
    echo "    $BASEFILENAME..."
    rm -f "$TESTDIR"/"$BASEFILENAME".{db,out,log,,err,diff}
    (
      cd "$TESTDIR" &&
        python -m feedspora --testing "$BASEFILENAME" \
          >"$BASEFILENAME".out \
          2>"$BASEFILENAME".log
    )
    # We actually hope that the grep DOES fail!
    # Regardless, we don't want the result of grep or diff operations
    # to stop test processing
    set +e 
    TESTERR=$(grep 'ERROR:' "${TESTDIR}"/"${BASEFILENAME}".log)
    if [ "X${TESTERR}" != "X" ]; then
      echo "        Execution errors encountered: see ${TESTDIR}/${BASEFILENAME}.err"
      ERROUT="${TESTDIR}/${BASEFILENAME}.err"
      echo "Execution errors (from ${TESTDIR}/${BASEFILENAME}.log):" > "${ERROUT}"
      echo "${TESTERR}" >> "${ERROUT}"
      PASSORFAIL=1
    fi
    TESTDIFF=$(diff "${TESTDIR}"/"${BASEFILENAME}".{au,out})
    if [ "X${TESTDIFF}" != "X" ]; then
      DIFFOUT="${TESTDIR}/${BASEFILENAME}.diff"
      echo "        Output variance detected: see ${DIFFOUT}"
      echo "Output variance between ${TESTDIR}/${BASEFILENAME}.{au,out}):" > "${DIFFOUT}"
      echo "${TESTDIFF}" >> "${DIFFOUT}"
      PASSORFAIL=1
    fi
    set -e
  done
}

case "${1:-}" in
all)
  echo "Executing all tests"
  echo "Executing feed tests"
  execute_tests "test_feed"
  echo "Executing post tests"
  execute_tests "test_post"
  ;;
feed)
  echo "Executing feed tests"
  execute_tests "test_feed"
  ;;
post)
  echo "Executing post tests"
  execute_tests "test_post"
  ;;
*)
  echo "No or Unknown test specification '${1:-}' - aborting"
  echo "${0:-} all | feed | post"
  exit 1
  ;;
esac

echo "All specified tests executed"
if [ $PASSORFAIL == 1 ]; then
  echo "FAILED"
else
  echo "PASSED"
fi
exit $PASSORFAIL

