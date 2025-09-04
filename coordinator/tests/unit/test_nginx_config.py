import pytest

import nginx_config


@pytest.mark.parametrize(
    "port",
    [
        4040,
        4209,
    ],
)
def test_upstreams_contain_correct_port(port):
    # GIVEN a port number

    # WHEN upstreams configuration is generated
    upstream_config = nginx_config.upstreams(port)

    # THEN it contains the correct port
    for upstream in upstream_config:
        assert upstream.port == port


def test_servers_config():
    # GIVEN information if tls is enabled

    # WHEN a mapping of server ports is generated
    server_ports_to_locations = nginx_config.server_ports_to_locations()

    # THEN the locations are mapped to the right port
    assert server_ports_to_locations[nginx_config.http_server_port]
