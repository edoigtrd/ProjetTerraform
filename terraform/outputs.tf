output "connection_string" {
  value     = local.database_url
  sensitive = true
}

output "hello_world_function_url" {
  value = "https://${scaleway_function.hello_world.domain_name}"
}

output "dashboard_url" {
  value = scaleway_container.dashboard.public_endpoint
}
