#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

pass_or_fail=0
function execute_tests() {
  test_dir=$1
  for config in "${test_dir}"/*.yml; do
    filename=$(basename -- "$config")
    test="${filename%.*}"
    echo "    $test..."
    rm -f "${test_dir}"/"${test}".{db,out,log,,err,diff}
    (cd "${test_dir}" && python -m feedspora --testing "$test" > "${test}".out 2> "${test}".log)
    # We actually hope that the grep DOES fail!
    # Regardless, we don't want the result of grep or diff operations
    # to stop test processing
    set +e 
    test_err=$(grep 'ERROR:' "${test_dir}"/"${test}".log)
    if [ "X${test_err}" != "X" ]; then
      echo "        Execution errors encountered: see ${test_dir}/${test}.err"
      err_out="${test_dir}/${test}.err"
      echo "Execution errors (from ${test_dir}/${test}.log):" > "${err_out}"
      echo "${test_err}" >> "${err_out}"
      pass_or_fail=1
    fi
    test_diff=$(diff "${test_dir}"/"${test}".{au,out})
    if [ "X${test_diff}" != "X" ]; then
      diff_out="${test_dir}/${test}.diff"
      echo "        Output variance detected: see ${diff_out}"
      echo "Output variance between ${test_dir}/${test}.{au,out}):" > "${diff_out}"
      echo "${test_diff}" >> "${diff_out}"
      pass_or_fail=1
    fi
    set -e
  done
}

test_feed=0
test_post=0
show_usage=0
if [ "X${1:-}" = "X" ]; then
  echo "No tests specified - aborting"
  show_usage=1
elif [ "${1:-}" = "all" ]; then
  echo "Executing all tests"
  test_feed=1
  test_post=1
elif [ "${1:-}" = "feed" ]; then
  test_feed=1
elif [ "${1:-}" = "post" ]; then
  test_post=1
else
  echo "Unknown test specification '${1:-}' - aborting"
  show_usage=1
fi
if [ $show_usage == 1 ]; then
  echo "$0 all | feed | post"
  exit 1
fi
if [ $test_feed == 1 ]; then
  echo "Executing feed tests"
  execute_tests "test_feed"
fi
if [ $test_post == 1 ]; then
  echo "Executing post tests"
  execute_tests "test_post"
fi
echo "All specified tests executed"
if [ $pass_or_fail == 1 ]; then
  echo "FAILED"
else
  echo "PASSED"
fi
exit $pass_or_fail

