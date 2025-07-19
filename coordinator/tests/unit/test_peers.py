import json
import socket

import pytest
from ops.testing import PeerRelation, State

from charm import PyroscopeCoordinatorCharm


@pytest.mark.parametrize(
    "fqdns", (["matterhost", "localmost"], ["matter.host"], [], None)
)
def test_peer_fqdns(
    context, s3, all_worker, nginx_container, nginx_prometheus_exporter_container, fqdns
):
    if fqdns is not None:
        # unit 0 is us.
        peer_data = {i + 1: {"fqdn": json.dumps(fqdn)} for i, fqdn in enumerate(fqdns)}
        peers = [
            PeerRelation(
                "peers",
                # omit value to let default kick in
                **({"peers_data": peer_data} if peer_data else {}),
            )
        ]
    else:
        peers = []

    with context(
        context.on.update_status(),
        State(
            relations=[s3, all_worker, *peers],
            containers=[nginx_container, nginx_prometheus_exporter_container],
            leader=True,
        ),
    ) as mgr:
        charm: PyroscopeCoordinatorCharm = mgr.charm
        assert set(charm._peers.get_fqdns()) == {*(fqdns or {}), socket.getfqdn()}
