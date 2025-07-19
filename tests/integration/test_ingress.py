#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import subprocess

import requests
import tenacity
from tenacity import wait_exponential as wexp, stop_after_attempt as satt
import jubilant
import pytest
from jubilant import Juju

from helpers import (
    PYROSCOPE_APP,
    WORKER_APP,
    deploy_monolithic_cluster,
    TRAEFIK_APP,
    get_ingress_proxied_hostname,
    get_unit_ip_address,
)

# hardcoded here instead of imported from coordinator.src.nginx_config to avoid dependency and PYTHONPATH conflicts
NGINX_CONFIG_HTTP_SERVER_PORT = 8080
NGINX_CONFIG_GRPC_SERVER_PORT = 42424

logger = logging.getLogger(__name__)


@tenacity.retry(wait=wexp(multiplier=2, max=30), stop=satt(10))
def check_http_endpoint(juju: Juju, use_ingress: bool):
    if use_ingress:
        ingress_ip = get_ingress_proxied_hostname(juju)
        url = f"http://{ingress_ip}/{juju.model}-{PYROSCOPE_APP}"
    else:
        nginx_ip = get_unit_ip_address(juju, PYROSCOPE_APP, 0)
        url = f"http://{nginx_ip}:{NGINX_CONFIG_HTTP_SERVER_PORT}"

    ui = requests.get(url)
    assert b"Grafana Pyroscope" in ui.content


@tenacity.retry(wait=wexp(multiplier=2, max=30), stop=satt(10))
def check_grpc_endpoint(juju: Juju, use_ingress: bool):
    if use_ingress:
        hostname = get_ingress_proxied_hostname(juju)
    else:
        hostname = get_unit_ip_address(juju, PYROSCOPE_APP, 0)

    url = f"http://{hostname}:{NGINX_CONFIG_GRPC_SERVER_PORT}"
    proc = subprocess.run(["curl", url], capture_output=True, text=True, check=False)

    if use_ingress:
        assert "Welcome to nginx!" in proc.stdout
    else:
        # this is the response you get by curling a grpc server, and that's all we want to verify in this test
        assert "Received HTTP/0.9 when not allowed" in proc.stderr


@pytest.mark.setup
def test_setup(juju: Juju):
    # GIVEN an empty model
    # WHEN deploying the tempo cluster and traefik
    juju.deploy("traefik-k8s", app=TRAEFIK_APP, channel="latest/stable", trust=True)
    deploy_monolithic_cluster(juju)


def test_nginx_ui_route_before_ingress(juju: Juju):
    """Verify that before we integrate ingress, we can hit the http endpoint through nginx."""
    check_http_endpoint(juju, use_ingress=False)


def test_nginx_grpc_server_route_before_ingress(juju: Juju):
    """Verify that before we integrate ingress, we can hit the grpc endpoint through nginx."""
    check_grpc_endpoint(juju, use_ingress=False)


@pytest.mark.setup
def test_add_ingress(juju):
    # AND WHEN we integrate the tempo cluster with traefik over ingress
    juju.integrate(PYROSCOPE_APP + ":ingress", TRAEFIK_APP)

    # THEN the coordinator, worker, and traefik are all in active/idle state
    juju.wait(
        lambda status: jubilant.all_active(
            status, TRAEFIK_APP, PYROSCOPE_APP, WORKER_APP
        ),
        error=jubilant.any_error,
        timeout=2000,
    )


def test_nginx_ui_route_with_ingress(juju: Juju):
    """Verify that once we integrate ingress, we can hit the http endpoint through nginx."""
    check_http_endpoint(juju, use_ingress=True)


def test_nginx_grpc_server_route_with_ingress(juju: Juju):
    """Verify that once we integrate ingress, we can hit the grpc endpoint through nginx."""
    check_grpc_endpoint(juju, use_ingress=True)


@pytest.mark.teardown
def test_remove_ingress(juju: Juju):
    # GIVEN a model with traefik and the tempo cluster integrated
    # WHEN we remove the ingress relation
    juju.remove_relation(PYROSCOPE_APP + ":ingress", TRAEFIK_APP)

    # THEN the coordinator and worker are in active/idle state
    juju.wait(
        lambda status: jubilant.all_active(status, PYROSCOPE_APP, WORKER_APP),
        error=jubilant.any_error,
        timeout=2000,
    )


def test_nginx_ui_route_after_ingress(juju: Juju):
    """Verify that after we remove ingress, we can once again hit the http endpoint through nginx."""
    check_http_endpoint(juju, use_ingress=False)


def test_nginx_grpc_server_route_after_ingress(juju: Juju):
    """Verify that after we remove ingress, we can once again hit the grpc endpoint through nginx."""
    check_grpc_endpoint(juju, use_ingress=False)


@pytest.mark.teardown
def test_teardown(juju: Juju):
    # GIVEN a model with traefik and the tempo cluster
    # WHEN we remove traefik, the coordinator, and the worker
    juju.remove_application(PYROSCOPE_APP)
    juju.remove_application(WORKER_APP)
    juju.remove_application(TRAEFIK_APP)

    # THEN nothing throws an exception
