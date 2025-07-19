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


@pytest.mark.parametrize("tls", (True, False))
def test_servers_config(tls):
    # GIVEN information if tls is enabled

    # WHEN a mapping of server ports is generated
    server_ports_to_locations = nginx_config.server_ports_to_locations(
        tls_available=tls
    )

    # THEN the locations are mapped to the right port
    assert server_ports_to_locations[
        nginx_config.https_server_port if tls else nginx_config.http_server_port
    ]

    # AND THEN the other port isn't in the configuration
    assert (
        server_ports_to_locations.get(
            nginx_config.http_server_port if tls else nginx_config.https_server_port
        )
        is None
    )
