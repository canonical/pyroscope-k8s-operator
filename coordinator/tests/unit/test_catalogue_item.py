from unittest.mock import patch

import ops

from ops.testing import State, Model
import pytest
from conftest import tls_patch


@pytest.mark.parametrize(
    "tls, expected_url",
    ((False, "http://foo.com:8080"), (True, "https://foo.com:8080")),
)
def test_catalogue_no_ingress(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
    catalogue,
    peers,
    tls,
    expected_url,
):
    with tls_patch(tls):
        state_out = context.run(
            context.on.update_status(),
            State(
                relations=[peers, s3, all_worker, catalogue],
                containers=[nginx_container, nginx_prometheus_exporter_container],
                unit_status=ops.ActiveStatus(),
                leader=True,
            ),
        )
    catalogue_out = state_out.get_relation(catalogue.id)
    assert catalogue_out.local_app_data["url"] == expected_url


@pytest.mark.parametrize(
    "tls, expected_url",
    (
        (False, "http://pyroscope-coordinator-k8s.test.svc.cluster.local:8080"),
        (True, "https://pyroscope-coordinator-k8s.test.svc.cluster.local:8080"),
    ),
)
def test_catalogue_with_k8s_fqdn(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
    catalogue,
    peers,
    tls,
    expected_url,
):
    with tls_patch(tls):
        with patch(
            "socket.getfqdn",
            new=lambda: "something-something.something-else.svc.cluster.local",
        ):
            state_out = context.run(
                context.on.update_status(),
                State(
                    relations=[peers, s3, all_worker, catalogue],
                    containers=[nginx_container, nginx_prometheus_exporter_container],
                    unit_status=ops.ActiveStatus(),
                    leader=True,
                    model=Model(name="test"),
                ),
            )
    catalogue_out = state_out.get_relation(catalogue.id)
    assert catalogue_out.local_app_data["url"] == expected_url


@pytest.mark.parametrize(
    "tls, expected_url",
    (
        (False, "http://example.com/test-pyroscope-coordinator-k8s"),
        (True, "https://example.com/test-pyroscope-coordinator-k8s"),
    ),
)
def test_catalogue_ingress(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
    catalogue,
    ingress,
    ingress_with_tls,
    external_host,
    peers,
    tls,
    expected_url,
):
    state_out = context.run(
        context.on.update_status(),
        State(
            relations=[
                peers,
                s3,
                ingress_with_tls if tls else ingress,
                all_worker,
                catalogue,
            ],
            containers=[nginx_container, nginx_prometheus_exporter_container],
            unit_status=ops.ActiveStatus(),
            leader=True,
            model=Model(name="test"),
        ),
    )
    catalogue_out = state_out.get_relation(catalogue.id)
    assert catalogue_out.local_app_data["url"] == expected_url
