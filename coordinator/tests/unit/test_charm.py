import pytest
from ops.testing import State


@pytest.fixture(params=(True, False))
def base_state(request, s3, nginx_container, nginx_prometheus_exporter_container):
    return State(
        leader=request.param,
        relations=[s3],
        containers=[nginx_container, nginx_prometheus_exporter_container],
    )


def test_smoke(context, base_state):
    # verify the charm runs at all with and without leadership
    context.run(context.on.start(), base_state)
