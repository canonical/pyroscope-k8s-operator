#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Peer relation for pyroscope coordinators to exchange fqdns."""

from typing import List, Optional

import ops
from cosl.interfaces.utils import DatabagModel

PEERS_RELATION_ENDPOINT_NAME = "peers"


class PeerData(DatabagModel):
    """Databag model for the "peers" relation between coordinator units."""

    fqdn: str
    """FQDN hostname of this coordinator unit."""


class Peers:
    """Thin wrapper around a peer relation for the coordinator units to share data."""

    def __init__(self, relation: Optional[ops.Relation], hostname: str, unit: ops.Unit):
        self._relation = relation
        self._hostname = hostname
        self._unit = unit

    def reconcile(self) -> None:
        """Update peer unit data bucket with this unit's hostname."""
        relation = self._relation
        if not (relation and relation.data):
            return

        PeerData(fqdn=self._hostname).dump(relation.data[self._unit])

    @staticmethod
    def _get_peer_data(relation: ops.Relation, unit: ops.Unit) -> PeerData:
        """Get peer data from a given unit data bucket."""
        return PeerData.load(relation.data.get(unit, {}))

    def get_fqdns(self) -> List[str]:
        """Obtain from peer data all peer unit fqdns (including this unit)."""
        relation = self._relation
        if not (relation and relation.data):
            return [self._hostname]

        return [self._get_peer_data(relation, peer).fqdn for peer in relation.units] + [
            self._hostname
        ]
