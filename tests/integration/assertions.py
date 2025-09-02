#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import subprocess
import shlex
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def assert_profile_is_ingested(
    hostname: str,
    service_name: str = "profilegen",
    tls: bool = False,
    ca_path: Optional[Path] = None,
    server_name: Optional[str] = None,
):
    scheme = f"http{'s' if tls else ''}"
    port = "443" if tls else "8080"
    target_hostname = server_name or hostname

    cmd = (
        "curl -s --get --data-urlencode "
        f"'query=process_cpu:cpu:nanoseconds:cpu:nanoseconds{{service_name=\"{service_name}\"}}' "
        '--data-urlencode "from=now-1h" '
        f"{scheme}://{target_hostname}:{port}/pyroscope/render"
    )

    if ca_path:
        cmd += f" --cacert {str(ca_path)}"
    if server_name:
        cmd += f" --resolve {target_hostname}:{port}:{hostname}"

    logger.info(f"running: {cmd!r}")
    out = subprocess.run(shlex.split(cmd), text=True, capture_output=True)
    flames = json.loads(out.stdout)

    # equivalent to: jq -r '.flamebearer.levels[0] | add'"
    tot_levels = sum(flames["flamebearer"]["levels"][0])
    # if there's no data, this will be a zeroes array.
    assert tot_levels > 0, f"No data in graph obtained by {cmd}"
