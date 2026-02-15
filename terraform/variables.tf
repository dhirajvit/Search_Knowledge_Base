variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Terraform Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (dev)"
  type        = string
  validation {
    condition     = contains(["dev"], var.environment)
    error_message = "Terraform Environment must be one of: dev"
  }
}

variable "bedrock_model_id" {
  description = "Bedrock model ID"
  type        = string
  default     = "amazon.nova-lite-v1:0"
}

variable "bedrock_embed_model_id" {
  description = "bedrock_embed_model_id"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "api_daily_quota" {
  description = "API Gateway daily request quota"
  type        = number
  default     = 5
}

variable "lambda_timeout" {
  description = "Timeout in seconds for the Lambda function"
  type        = number
  default     = 30
}