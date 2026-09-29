#!/usr/bin/env bash
# Runs the whole suite against one version of the app.
#   ./run-tests.sh v7_8   -> tests cinemeter-v7_8.html
#   ./run-tests.sh v7_9   -> tests cinemeter-v7_9.html
set -u
V=${1:-v7_8}
node extract.mjs ../cinemeter-$V.html cinemeter-logic-$V.mjs >/dev/null
export CINEMETER_LOGIC=../cinemeter-logic-$V.mjs CINEMETER_HTML=../../cinemeter-$V.html
mkdir -p results
node --test --experimental-test-coverage --test-coverage-include="cinemeter-logic-$V.mjs" \
  --test-reporter=spec --test-reporter-destination=results/$V-spec.txt \
  --test-reporter=junit --test-reporter-destination=results/$V-junit.xml \
  test/*.test.mjs
