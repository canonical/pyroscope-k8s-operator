# Copyright 2025 Canonical
# See LICENSE file for licensing details.
"""Coordinator's Traefik configuration for traefik_route.

Pyroscope accepts http traffic (e.g. to serve the UI) and grpc traffic (to ingest profiles)
on the same port (4040).
Traefik and Nginx don't support that.
Therefore, we use the following routing strategy. For grpc traffic:

    traefik:42424 --> coordinator(nginx):42424 --> worker:4040

And for http traffic:

    traefik/<model-name>-<coordinator-app-name> --> coordinator(nginx):8080 --> worker:4040
"""

import dataclasses
from collections import namedtuple
from typing import Dict, Iterable, List, Literal, Callable

_REDIRECT_MIDDLEWARE_SUFFIX = "-redirect"


@dataclasses.dataclass
class Endpoint:
    """Represents an endpoint on the coordinator."""

    entrypoint_name: str
    protocol: Literal["http", "grpc"]
    port: int

    @property
    def sanitized_entrypoint_name(self) -> str:
        return self.entrypoint_name.replace("_", "-")


def _generate_http_routers_config(
    endpoints: Iterable[Endpoint],
    service_name_getter: Callable[[Endpoint], str],
    router_name_getter: Callable[[Endpoint], str],
    redirect_middleware_name: Callable[[Endpoint], str],
    stripprefix_middleware_name: str,
    tls: bool,
    prefix: str,
):
    http_routers = {}

    for endpoint in endpoints:
        redirect_middleware = redirect_middleware_name(endpoint) if tls else None
        if endpoint.protocol == "grpc":
            http_routers[router_name_getter(endpoint)] = {
                "entryPoints": [endpoint.sanitized_entrypoint_name],
                "service": service_name_getter(endpoint),
                # TODO better matcher
                "rule": "ClientIP(`0.0.0.0/0`)",
                # Omit 'middlewares' altogether if empty; else we get:
                # level=error msg="Error occurred during watcher callback:
                # ...: middlewares cannot be a standalone element (type map[string]*dynamic.Middleware)"
                **({"middlewares": [redirect_middleware]} if tls else {}),
            }

        else:
            http_routers[router_name_getter(endpoint)] = {
                "entryPoints": [endpoint.sanitized_entrypoint_name],
                "service": service_name_getter(endpoint),
                "rule": f"PathPrefix(`{prefix}`)",
                "middlewares": [stripprefix_middleware_name]
                + ([redirect_middleware] if tls else []),
            }

    return http_routers


def _generate_http_middlewares_config(
    endpoints: Iterable[Endpoint],
    redirect_middleware_name_getter: Callable[[Endpoint], str],
    tls: bool,
    prefix: str,
    stripprefix_middleware_name: str,
):
    middlewares = {
        stripprefix_middleware_name: {
            "stripPrefix": {"forceSlash": False, "prefixes": [prefix]}
        }
    }

    # only activate redirect middlewares if we have TLS
    if not tls:
        return middlewares

    for endpoint in endpoints:
        redirect_middleware = {
            redirect_middleware_name_getter(endpoint): {
                "redirectScheme": {
                    "permanent": True,
                    "port": endpoint.port,
                    "scheme": "https",
                }
            }
        }
        middlewares.update(redirect_middleware)
    return middlewares


def _generate_http_services_config(
    endpoints: Iterable[Endpoint],
    service_name_getter: Callable[[Endpoint], str],
    tls: bool,
    coordinator_fqdns: List[str],
):
    http_services = {}
    for endpoint in endpoints:
        if endpoint.protocol == "grpc" and not tls:
            # to send data to unsecured GRPC endpoints, we need h2c
            # see https://doc.traefik.io/traefik/v2.0/user-guides/grpc/#with-http-h2c
            http_services[service_name_getter(endpoint)] = {
                "loadBalancer": {
                    "servers": _build_lb_server_config(
                        "h2c", endpoint.port, coordinator_fqdns
                    )
                }
            }
        else:
            # anything else, including secured GRPC, can use _internal_url
            # ref https://doc.traefik.io/traefik/v2.0/user-guides/grpc/#with-https
            http_services[service_name_getter(endpoint)] = {
                "loadBalancer": {
                    "servers": _build_lb_server_config(
                        "https" if tls else "http", endpoint.port, coordinator_fqdns
                    )
                }
            }
    return http_services


def ingress_config(
    endpoints: Iterable[Endpoint],
    coordinator_fqdns: List[str],
    model_name: str,
    app_name: str,
    tls: bool,
    prefix: str,
) -> dict:
    """Build a raw ingress configuration for Traefik."""

    def redirect_middleware_name_getter(endpoint: Endpoint):
        return f"juju-{model_name}-{app_name}-middleware-{endpoint.sanitized_entrypoint_name}-redirect"

    def service_name_getter(endpoint: Endpoint):
        return (
            f"juju-{model_name}-{app_name}-service-{endpoint.sanitized_entrypoint_name}"
        )

    def router_name_getter(endpoint: Endpoint):
        return (
            f"juju-{model_name}-{app_name}-router-{endpoint.sanitized_entrypoint_name}"
        )

    # global strip-prefix middleware, applied to all routes
    stripprefix_middleware_name = f"juju-{model_name}-{app_name}-middleware-stripprefix"

    return {
        "http": {
            "routers": _generate_http_routers_config(
                endpoints,
                service_name_getter=service_name_getter,
                router_name_getter=router_name_getter,
                stripprefix_middleware_name=stripprefix_middleware_name,
                redirect_middleware_name=redirect_middleware_name_getter,
                tls=tls,
                prefix=prefix,
            ),
            "services": _generate_http_services_config(
                endpoints,
                service_name_getter=service_name_getter,
                coordinator_fqdns=coordinator_fqdns,
                tls=tls,
            ),
            "middlewares": _generate_http_middlewares_config(
                endpoints,
                redirect_middleware_name_getter=redirect_middleware_name_getter,
                stripprefix_middleware_name=stripprefix_middleware_name,
                prefix=prefix,
                tls=tls,
            ),
        }
    }


def _build_lb_server_config(
    scheme: str, port: int, coordinator_fqdns: List[str]
) -> List[Dict[str, str]]:
    """build the server portion of the loadbalancer config of Traefik ingress."""
    return [{"url": f"{scheme}://{fqdn}:{port}"} for fqdn in coordinator_fqdns]


def static_ingress_config(endpoints: List[Endpoint]):
    """Static portion of the traefik-route ingress configuration."""
    return {
        "entryPoints": {
            endpoint.entrypoint_name.replace("_", "-"): {"address": f":{endpoint.port}"}
        }
        for endpoint in endpoints
        if endpoint.protocol == "grpc"
    }


_TraefikConfig = namedtuple("_TraefikConfig", "static, dynamic")


def traefik_config(
    http_port: int,
    grpc_port: int,
    coordinator_fqdns: List[str],
    model_name: str,
    app_name: str,
    tls: bool,
    prefix: str,
) -> _TraefikConfig:
    """Generate static and dynamic traefik configuration."""
    endpoints = [
        Endpoint(entrypoint_name="web", protocol="http", port=http_port),
        Endpoint(
            entrypoint_name="pyroscope-grpc-server",
            protocol="grpc",
            port=grpc_port,
        ),
    ]

    return _TraefikConfig(
        dynamic=ingress_config(
            endpoints,
            coordinator_fqdns=coordinator_fqdns,
            model_name=model_name,
            app_name=app_name,
            tls=tls,
            prefix=prefix,
        ),
        static=static_ingress_config(endpoints),
    )
