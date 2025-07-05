output "app_name" {
  value = juju_application.pyroscope_coordinator.name
}

output "endpoints" {
  value = {
    # Requires
    certificates     = "certificates",
    ingress          = "ingress",
    logging          = "logging",
    charm_tracing    = "charm-tracing",
    workload_tracing = "workload-tracing",
    s3               = "s3",
    catalogue        = "catalogue",
    # Provides
    grafana_dashboard = "grafana-dashboard",
    send_datasource   = "send-datasource",
    metrics_endpoint  = "metrics-endpoint",
    pyroscope_cluster = "pyroscope-cluster",
  }
}