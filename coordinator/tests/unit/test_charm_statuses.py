import ops
from conftest import k8s_patch
from ops.testing import PeerRelation, State


def test_monolithic_status_no_s3_no_workers(
    context, nginx_container, nginx_prometheus_exporter_container
):
    state_out = context.run(
        context.on.start(),
        State(
            unit_status=ops.ActiveStatus(),
            containers=[nginx_container, nginx_prometheus_exporter_container],
            leader=True,
        ),
    )
    assert state_out.unit_status.name == "blocked"


def test_scaled_status_no_s3(
    context, nginx_container, nginx_prometheus_exporter_container
):
    state_out = context.run(
        context.on.start(),
        State(
            relations=[PeerRelation("peers", peers_data={1: {}, 2: {}})],
            containers=[nginx_container, nginx_prometheus_exporter_container],
            unit_status=ops.ActiveStatus(),
        ),
    )
    assert state_out.unit_status.name == "blocked"


def test_scaled_status_no_workers(
    context, nginx_container, nginx_prometheus_exporter_container
):
    state_out = context.run(
        context.on.start(),
        State(
            relations=[PeerRelation("peers", peers_data={1: {}, 2: {}})],
            containers=[nginx_container, nginx_prometheus_exporter_container],
            unit_status=ops.ActiveStatus(),
        ),
    )
    assert state_out.unit_status.name == "blocked"


def test_scaled_status_with_s3_and_workers(
    context, s3, all_worker, nginx_container, nginx_prometheus_exporter_container
):
    state_out = context.run(
        context.on.start(),
        State(
            relations=[
                PeerRelation("peers", peers_data={1: {}, 2: {}}),
                s3,
                all_worker,
            ],
            containers=[nginx_container, nginx_prometheus_exporter_container],
            unit_status=ops.ActiveStatus(),
            leader=True,
        ),
    )
    assert state_out.unit_status.name == "active"


def test_happy_status(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
):
    state_out = context.run(
        context.on.start(),
        State(
            relations=[
                PeerRelation("peers", peers_data={1: {}, 2: {}}),
                s3,
                all_worker,
            ],
            containers=[nginx_container, nginx_prometheus_exporter_container],
            unit_status=ops.ActiveStatus(),
            leader=True,
        ),
    )
    assert state_out.unit_status.name == "active"


@k8s_patch(status=ops.BlockedStatus("`juju trust` this application"))
def test_k8s_patch_failed(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
):
    state_out = context.run(
        context.on.update_status(),
        State(
            relations=[
                PeerRelation("peers", peers_data={1: {}, 2: {}}),
                s3,
                all_worker,
            ],
            containers=[nginx_container, nginx_prometheus_exporter_container],
            unit_status=ops.ActiveStatus(),
            leader=True,
        ),
    )
    assert state_out.unit_status == ops.BlockedStatus("`juju trust` this application")


@k8s_patch(status=ops.WaitingStatus("waiting"))
def test_k8s_patch_waiting(
    context,
    s3,
    all_worker,
    nginx_container,
    nginx_prometheus_exporter_container,
):
    state_out = context.run(
        context.on.update_status(),
        State(
            relations=[
                PeerRelation("peers", peers_data={1: {}, 2: {}}),
                s3,
                all_worker,
            ],
            containers=[nginx_container, nginx_prometheus_exporter_container],
            unit_status=ops.ActiveStatus(),
            leader=True,
        ),
    )
    assert state_out.unit_status == ops.WaitingStatus("waiting")
