# !/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import pytest
import requests
from jubilant import Juju, all_active, any_error
from tenacity import retry, stop_after_attempt, wait_fixed

from helpers import deploy_distributed_cluster, ALL_WORKERS, PYROSCOPE_APP, ALL_ROLES, get_unit_ip_address, \
    deploy_s3

PROMETHEUS_APP = "prometheus"
LOKI_APP = "loki"
TEMPO_APP = "tempo"
TEMPO_WORKER_APP = "tempo-worker"
TEMPO_S3_APP = "tempo-s3-bucket"
TEMPO_S3_BUCKET = "tempo"

logger = logging.getLogger(__name__)

SELF_MONITORING_STACK = (
PROMETHEUS_APP, LOKI_APP, TEMPO_WORKER_APP, TEMPO_APP, TEMPO_S3_APP
)

@pytest.mark.setup
def test_deploy_distributed_pyroscope(juju: Juju):
    # GIVEN an empty model
    # WHEN we deploy a pyroscope cluster with distributed workers
    # THEN the coordinator, s3 integrator, and all workers are in active/idle state
    deploy_distributed_cluster(juju, ALL_ROLES)


@pytest.mark.setup
def test_deploy_self_monitoring_stack(juju: Juju):
    # GIVEN a model
    # WHEN we deploy a monitoring stack
    juju.deploy("prometheus-k8s", app=PROMETHEUS_APP, channel="edge", trust=True)
    juju.deploy("loki-k8s", app=LOKI_APP, channel="edge", trust=True)

    # tracing
    juju.deploy("tempo-coordinator-k8s", app=TEMPO_APP, channel="edge", trust=True)
    juju.deploy("tempo-worker-k8s", app=TEMPO_WORKER_APP, channel="edge", trust=True)
    juju.integrate(TEMPO_APP, TEMPO_WORKER_APP)

    # deploys the s3 integrator and creates the bucket on the s3 backend
    deploy_s3(juju, bucket_name=TEMPO_S3_BUCKET, s3_integrator_app=TEMPO_S3_APP)
    juju.integrate(TEMPO_APP, TEMPO_S3_APP + ":s3-credentials")

    # THEN the monitoring stack is in active/idle state
    juju.wait(
        lambda status: all_active(status, *SELF_MONITORING_STACK),
        error=any_error,
        timeout=3000,
    )


@pytest.mark.setup
def test_relate_self_monitoring_stack(juju: Juju):
    # GIVEN a model with a pyroscope cluster, and a monitoring stack
    # WHEN we integrate the pyroscope cluster over self-monitoring relations
    juju.integrate(PYROSCOPE_APP + ":metrics-endpoint", PROMETHEUS_APP + ":metrics-endpoint")
    juju.integrate(PYROSCOPE_APP + ":logging", LOKI_APP + ":logging")
    juju.integrate(PYROSCOPE_APP + ":charm-tracing", TEMPO_APP + ":tracing")

    # THEN the coordinator, all workers, and the monitoring stack are all in active/idle state
    juju.wait(
        lambda status: all_active(status, TEMPO_APP, *ALL_WORKERS, *SELF_MONITORING_STACK),
        error=any_error,
        timeout=2000,
        delay=5,
        successes=12,
    )


@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def test_self_monitoring_metrics_ingestion(juju: Juju):
    # GIVEN a pyroscope cluster integrated with prometheus over metrics-endpoint
    address = get_unit_ip_address(juju, PROMETHEUS_APP, 0)
    # WHEN we query the metrics for the coordinator and each of the workers
    url = f"http://{address}:9090/api/v1/query"
    for app in (PYROSCOPE_APP, *ALL_WORKERS):
        params = {"query": f"up{{juju_application='{app}'}}"}
        # THEN we should get a successful response and at least one result
        try:
            response = requests.get(url, params=params)
            data = response.json()
            assert data["status"] == "success", f"Metrics query failed for app '{app}'"
            assert len(data["data"]["result"]) > 0, f"No metrics found for app '{app}'"
        except requests.exceptions.RequestException as e:
            assert False, f"Request to Prometheus failed for app '{app}': {e}"


@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def test_self_monitoring_charm_traces_ingestion(juju: Juju):
    # GIVEN a pyroscope cluster integrated with tempo over charm-tracing
    address = get_unit_ip_address(juju, TEMPO_APP, 0)
    # WHEN we query the tags for all ingested traces in Tempo
    url = f"http://{address}:3200/api/search/tag/juju_application/values"
    response = requests.get(url)
    tags = response.json()['tagValues']
    # THEN we can find each pyroscope charm has sent some charm traces
    for app in (PYROSCOPE_APP, ): # todo: add *ALL_WORKERS
        assert app in tags


@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def test_self_monitoring_logs_ingestion(juju: Juju):
    # GIVEN a pyroscope cluster integrated with loki over logging
    address = get_unit_ip_address(juju, LOKI_APP, 0)
    # WHEN we query the logs for each worker
    # Use query_range for a longer default time interval
    url = f"http://{address}:3100/loki/api/v1/query_range"
    for app in ALL_WORKERS:
        query = f'{{juju_application="{app}"}}'
        params = {"query": query}
        # THEN we should get a successful response and at least one result
        try:
            response = requests.get(url, params=params)
            data = response.json()
            assert data["status"] == "success", f"Log query failed for app '{app}'"
            assert len(data["data"]["result"]) > 0, f"No logs found for app '{app}'"
        except requests.exceptions.RequestException as e:
            assert False, f"Request to Loki failed for app '{app}': {e}"


@pytest.mark.teardown
def test_teardown_self_monitoring_stack(juju: Juju):
    # GIVEN a pyroscope cluster with self-monitoring relations
    # WHEN we remove the self-monitoring stack
    for app in SELF_MONITORING_STACK:
        juju.remove_application(app)

    # THEN the coordinator and all workers eventually reach active/idle state
    juju.wait(
        lambda status: all_active(status, PYROSCOPE_APP, *ALL_WORKERS),
        error=any_error,
        timeout=2000,
        delay=5,
        successes=3,
    )


@pytest.mark.teardown
def test_teardown_pyroscope(juju: Juju):
    for worker_name in ALL_WORKERS:
        juju.remove_application(worker_name)
    juju.remove_application(PYROSCOPE_APP)
