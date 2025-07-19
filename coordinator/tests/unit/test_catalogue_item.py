from unittest.mock import patch

import ops

import nginx_config
from ops.testing import State


def test_catalogue_no_ingress(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
    catalogue,
    peers,
):
    with patch("socket.getfqdn", new=lambda: "foo.com"):
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
    assert catalogue_out.local_app_data["url"] == "http://foo.com:8080"


def test_catalogue_with_k8s_fqdn(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
    catalogue,
    external_host,
    peers,
):
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
            ),
        )
    catalogue_out = state_out.get_relation(catalogue.id)
    assert (
        catalogue_out.local_app_data["url"]
        == f"http://pyroscope-coordinator-k8s.{state_out.model.name}.svc.cluster.local:{nginx_config.http_server_port}"
    )


def test_catalogue_ingress(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
    catalogue,
    ingress,
    external_host,
    peers,
):
    with patch("socket.getfqdn", new=lambda: "foo.com"):
        state_out = context.run(
            context.on.update_status(),
            State(
                relations=[peers, s3, ingress, all_worker, catalogue],
                containers=[nginx_container, nginx_prometheus_exporter_container],
                unit_status=ops.ActiveStatus(),
                leader=True,
            ),
        )
    catalogue_out = state_out.get_relation(catalogue.id)
    assert (
        catalogue_out.local_app_data["url"]
        == f"http://{external_host}/{state_out.model.name}-pyroscope-coordinator-k8s"
    )
