variable "project_id" {
  type        = string
  description = "Scaleway project ID"
}

variable "bsky_app_name" {
  type        = string
  description = "Bluesky handle used by the load_data job to authenticate"
}

variable "bsky_app_password" {
  type        = string
  description = "Bluesky app password used by the load_data job to authenticate"
  sensitive   = true
}

variable "openai_api_endpoint" {
  type        = string
  description = "OpenAI-compatible API endpoint used by the load_data job to classify posts"
}

variable "openai_api_key" {
  type        = string
  description = "API key for the OpenAI-compatible endpoint used by the load_data job"
  sensitive   = true
}