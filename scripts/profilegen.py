#!/usr/bin/env python3
"""Utility script to generate a mock CPU profile and export it using OTLP gRPC to a profiling backend (i.e. Pyroscope/Otel Collector)."""

import os
from typing import Optional
import grpc
from opentelemetry.proto.profiles.v1development import profiles_pb2
from opentelemetry.proto.collector.profiles.v1development import (
    profiles_service_pb2,
    profiles_service_pb2_grpc,
)
from opentelemetry.proto.common.v1 import common_pb2
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def _build_profile() -> profiles_pb2.Profile:
    sample_type = profiles_pb2.ValueType(
        # The indices will internally reference whatever is in the profile's dictionary's `string_table`
        type_strindex=1,  # "cpu"
        unit_strindex=2,  # "nanoseconds"
    )

    sample = profiles_pb2.Sample(
        locations_start_index=0,
        locations_length=1,
        value=[100],  # 1 nanosecond
        attribute_indices=[0],
    )

    return profiles_pb2.Profile(
        sample_type=[sample_type],
        sample=[sample],
        location_indices=[0],
        period_type=sample_type,
        period=1,
        default_sample_type_index=0,
    )


def _build_profile_dictionary(service_name: str) -> profiles_pb2.ProfilesDictionary:
    # index 0 must be "" (empty string) by convention
    string_table = [
        "",
        "cpu",
        "nanoseconds",
        "profilegen-main-function",
    ]

    function = profiles_pb2.Function(
        name_strindex=3,  # "profilegen-main-function"
    )

    location = profiles_pb2.Location(
        mapping_index=0,
        line=[
            profiles_pb2.Line(
                function_index=0,  # refers to first function in Profile.function
            )
        ],
    )

    attribute = common_pb2.KeyValue(
        key="service.name",
        value=common_pb2.AnyValue(string_value=service_name),
    )

    return profiles_pb2.ProfilesDictionary(
        string_table=string_table,
        location_table=[location],
        function_table=[function],
        mapping_table=[profiles_pb2.Mapping()],
        attribute_table=[attribute],
    )


def emit_profile(
    endpoint: str,
    service_name: str,
    insecure: bool,
    ca_path: Optional[str] = None,
    server_name: Optional[str] = None,
):
    profile = _build_profile()
    profile_dictionary = _build_profile_dictionary(service_name)

    request = profiles_service_pb2.ExportProfilesServiceRequest(
        resource_profiles=[
            profiles_pb2.ResourceProfiles(
                scope_profiles=[profiles_pb2.ScopeProfiles(profiles=[profile])],
            )
        ],
        dictionary=profile_dictionary,
    )

    if insecure:
        channel = grpc.insecure_channel(endpoint)
    else:
        ca_cert_bytes = (
            Path(ca_path).read_bytes() if ca_path and Path(ca_path).exists() else None
        )
        # override the server name as the certificate might not match the actual hostname we're connecting to
        options = (
            (("grpc.ssl_target_name_override", server_name),) if server_name else ()
        )
        channel = grpc.secure_channel(
            endpoint,
            grpc.ssl_channel_credentials(root_certificates=ca_cert_bytes),
            options=options,
        )
    stub = profiles_service_pb2_grpc.ProfilesServiceStub(channel)
    stub.Export(request)


if __name__ == "__main__":
    emit_profile(
        endpoint=os.getenv("PROFILEGEN_ENDPOINT", "127.0.0.1:4317"),
        service_name=os.getenv("PROFILEGEN_SERVICE", "profilegen-service"),
        insecure=os.getenv("PROFILEGEN_INSECURE", "True").lower() in ("true", "1"),
        ca_path=os.getenv("PROFILEGEN_CA_PATH", None),
        server_name=os.getenv("PROFILEGEN_SERVER_NAME", None),
    )
