#!/usr/bin/env bash

# util for running a single integration test module locally
export COORDINATOR_CHARM_PATH=./coordinator/pyroscope-coordinator-k8s_ubuntu@24.04-amd64.charm
export WORKER_CHARM_PATH=./worker/pyroscope-worker-k8s_ubuntu@24.04-amd64.charm

echo "usage: sh ./tests/integration/run_tests.sh test_foo [PYTEST_JUBILANT_OPTIONS]"
echo "RUNNING:" tox -e integration -- -k $1 "${@:2}"
tox -e integration -- -k $1 "${@:2}"