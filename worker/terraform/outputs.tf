output "app_name" {
  value = juju_application.pyroscope_worker.name
}

output "endpoints" {
  value = {
    # Requires
    pyroscope_cluster = "pyroscope-cluster"
    # Provides
  }
}