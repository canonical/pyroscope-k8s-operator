#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from jubilant import Juju, all_active, any_error
from tenacity import retry, stop_after_attempt, wait_fixed
from helpers import (
    deploy_monolithic_cluster,
    emit_profile,
    PYROSCOPE_APP,
    get_unit_ip_address,
    OTEL_COLLECTOR_APP,
    INTEGRATION_TESTERS_CHANNEL,
    WORKER_APP,
    SSC_APP,
)
from assertions import assert_profile_is_ingested


@pytest.mark.setup
def test_deploy_pyroscope(juju: Juju):
    deploy_monolithic_cluster(juju, wait_for_idle=False)


@pytest.mark.setup
def test_deploy_and_integrate_collector(juju: Juju):
    juju.deploy(
        "opentelemetry-collector-k8s",
        OTEL_COLLECTOR_APP,
        channel=INTEGRATION_TESTERS_CHANNEL,
        trust=True,
    )
    juju.integrate(f"{PYROSCOPE_APP}:profiling", OTEL_COLLECTOR_APP)
    juju.wait(
        lambda status: all_active(
            status, PYROSCOPE_APP, WORKER_APP, OTEL_COLLECTOR_APP
        ),
        timeout=10 * 60,
        error=lambda status: any_error(status, PYROSCOPE_APP, WORKER_APP),
        delay=10,
        successes=6,
    )


@pytest.mark.setup
def test_deploy_and_integrate_ssc(juju: Juju):
    juju.deploy("self-signed-certificates", SSC_APP)
    juju.integrate(f"{PYROSCOPE_APP}:certificates", SSC_APP)
    juju.integrate(f"{OTEL_COLLECTOR_APP}:receive-ca-cert", SSC_APP)
    juju.wait(
        lambda status: all_active(
            status, PYROSCOPE_APP, WORKER_APP, OTEL_COLLECTOR_APP
        ),
        timeout=10 * 60,
        error=lambda status: any_error(status, PYROSCOPE_APP, WORKER_APP),
        delay=10,
        successes=6,
    )


def test_emit_profile_to_collector(juju: Juju):
    collector_ip = get_unit_ip_address(juju, OTEL_COLLECTOR_APP, 0)
    emit_profile(
        endpoint=f"{collector_ip}:4317", service_name="profilegen-otel-collector"
    )


@retry(stop=stop_after_attempt(6), wait=wait_fixed(10))
def test_ingest_profile_from_collector(juju: Juju, ca_cert_path):
    pyroscope_ip = get_unit_ip_address(juju, PYROSCOPE_APP, 0)
    assert_profile_is_ingested(
        hostname=pyroscope_ip,
        service_name="profilegen-otel-collector",
        tls=True,
        ca_path=str(ca_cert_path),
        # pass server_name to avoid hostname mismatch
        server_name=f"{PYROSCOPE_APP}.{juju.model}.svc.cluster.local",
    )


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_relation(f"{PYROSCOPE_APP}:profiling", OTEL_COLLECTOR_APP)
    juju.wait(
        lambda status: all_active(status, PYROSCOPE_APP, WORKER_APP),
        timeout=10 * 60,
        error=lambda status: any_error(status, PYROSCOPE_APP, WORKER_APP),
        delay=10,
        successes=6,
    )
