#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

function execute_tests() {
  test_dir=$1
  for config in `ls ${test_dir}/*.yml`; do
    filename=$(basename -- "$config")
    test="${filename%.*}"
    echo "    $test..."
    rm -f ${test_dir}/${test}.out ${test_dir}/${test}.log ${test_dir}/${test}.db
    (cd ${test_dir} && python -m feedspora --testing $test > ${test}.out 2> ${test}.log)
    grep 'ERROR:' ${test_dir}/${test}.log
  done
}

test_feed=0
test_post=0
show_usage=0
if [ "X$1" = "X" ]; then
  echo "No tests specified - aborting"
  show_usage=1
elif [ "$1" = "all" ]; then
  echo "Executing all tests"
  test_feed=1
  test_post=1
elif [ "$1" = "feed" ]; then
  test_feed=1
elif [ "$1" = "post" ]; then
  test_post=1
else
  echo "Unknown test specification '$1' - aborting"
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

