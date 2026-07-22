output "connection_string" {
  value     = local.database_url
  sensitive = true
}
