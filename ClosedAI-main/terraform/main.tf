terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# Paste the Quadrant Internship subscription ID when you run Terraform.
variable "subscription_id" {
  description = "Azure subscription ID for the Quadrant Internship subscription."
  type        = string
}

# This name can be changed later. Azure Web App names must be globally unique.
variable "web_app_name" {
  description = "Globally unique name for the Next.js Azure Web App."
  type        = string
  default     = "closed-ai-hr-copilot-dev"
}

# F1 is the cheapest/free App Service tier. Change this later if your mentor requests it.
variable "app_service_sku" {
  description = "Azure App Service Plan SKU."
  type        = string
  default     = "F1"
}

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id
}

# Use the resource group that already exists.
# Terraform will NOT create or delete the Closed_AI resource group.
data "azurerm_resource_group" "closed_ai" {
  name = "Closed_AI"
}

# Hosting plan for the Next.js frontend.
resource "azurerm_service_plan" "frontend" {
  name                = "closed-ai-frontend-plan"
  resource_group_name = data.azurerm_resource_group.closed_ai.name
  location            = data.azurerm_resource_group.closed_ai.location

  os_type  = "Linux"
  sku_name = var.app_service_sku

  tags = {
    Project     = "AI-HR-Copilot"
    Environment = "Development"
    ManagedBy   = "Terraform"
  }
}

# Linux Azure Web App for the current Next.js frontend.
resource "azurerm_linux_web_app" "frontend" {
  name                = var.web_app_name
  resource_group_name = data.azurerm_resource_group.closed_ai.name
  location            = data.azurerm_resource_group.closed_ai.location
  service_plan_id     = azurerm_service_plan.frontend.id
  https_only          = true

  site_config {
    always_on        = false
    app_command_line = "npm start"

    application_stack {
      node_version = "20-lts"
    }
  }

  app_settings = {
    NODE_ENV                       = "production"
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    WEBSITE_RUN_FROM_PACKAGE       = "1"
  }

  tags = {
    Project     = "AI-HR-Copilot"
    Environment = "Development"
    ManagedBy   = "Terraform"
  }
}

output "resource_group_name" {
  description = "Existing Azure resource group used by this project."
  value       = data.azurerm_resource_group.closed_ai.name
}

output "frontend_web_app_name" {
  description = "Name of the created frontend Azure Web App."
  value       = azurerm_linux_web_app.frontend.name
}

output "frontend_url" {
  description = "Default URL of the frontend Azure Web App."
  value       = "https://${azurerm_linux_web_app.frontend.default_hostname}"
}
