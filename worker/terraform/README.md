# Terraform module for pyroscope-worker-k8s

This is a Terraform module facilitating the deployment of pyroscope-worker-k8s charm, using the [Terraform juju provider](https://github.com/juju/terraform-provider-juju/). For more information, refer to the provider [documentation](https://registry.terraform.io/providers/juju/juju/latest/docs). 


## Requirements
This module requires a `juju` model to be available. Refer to the [usage section](#usage) below for more details.

## API

### Inputs
The module offers the following configurable inputs:

| Name | Type | Description | Default |
| - | - | - | - |
| `app_name`| string | Name to give the deployed application | pyroscope-worker |
| `channel`| string | Channel that the charm is deployed from |  |
| `config`| map(string) | Map of the charm configuration options | {} |
| `constraints`| string | String listing constraints for this application | arch=amd64 |
| `model`| string | Reference to an existing model resource or data source for the model to deploy to |  |
| `revision`| number | Revision number of the charm |  |
| `storage_directives`| map(string) | Map of storage used by the application, which defaults to 1 GB, allocated by Juju. | {} |
| `units`| number | Unit count/scale | 1 |

### Outputs
Upon application, the module exports the following outputs:

| Name | Type | Description |
| - | - | - |
| `app_name`| string | Name of the deployed application |
| `endpoints`| map(string) | Map of all `provides` and `requires` endpoints |

## Usage

> [!NOTE]
> This module is intended to be used only in conjunction with its counterpart, [pyroscope coordinator module](https://github.com/canonical/pyroscope-k8s-operator/coordinator) and, when deployed in isolation, is not functional. 
> For the pyroscope HA solution module deployment, check [pyroscope HA module](https://github.com/canonical/observability)

### Basic usage
In order to deploy this standalone module, create a `main.tf` file with the following content:
```hcl
module "pyroscope-worker" {
  source      = "git::https://github.com/canonical/pyroscope-k8s-operator//worker/terraform"
  model_name  = var.model_name
  app_name    = var.app_name
  channel     = var.channel
  config      = var.config
  revision    = var.revision
  units       = var.units
  constraints = var.constraints
}
variable "app_name" {
  description = "Application name"
  type        = string
  default     = "pyroscope-worker"
}
variable "channel" {
  description = "Charm channel"
  type        = string
  default     = "2/edge"
}
variable "config" {
  description = "Charm config options as in the ones we pass in juju config"
  type        = map(any)
  default     = {}
}
variable "model_name" {
  description = "Model name"
  type        = string
}
variable "revision" {
  description = "Charm revision"
  type        = number
  default     = null
}
variable "units" {
  description = "Number of units"
  type        = number
  default     = 1
}
variable "constraints" {
  description = "Constraints for the charm deployment"
  type        = string
  default     = "arch=amd64"
}
```
Then, use terraform to deploy the module:
```
terraform init
terraform apply -var="model_name=<MODEL_NAME>" -auto-approve
```

### Deploy with constraints

In order to deploy this module with a set of constraints (e.g: architecture, anti-affinity rules, etc.), create a `main.tf` similar to the [basic usage `main.tf` file](#basic-usage). 

Then, create a `constraints.tfvars` file with the following content:
```hcl
model_name = <model-name>
constraints = "arch=<desired-arch> mem=<desired-memory>"
```
> [!NOTE]
> See [Juju constraints](https://documentation.ubuntu.com/juju/latest/reference/constraint/#list-of-constraints) for a list of available juju constraints.

Then, use terraform to deploy the module:
```
terraform init
terraform apply -var-file=constraints.tfvars
```
> [!NOTE]
> Any constraints must be prepended with "`arch=<desired-arch> `" for Terraform operations to work.
>
> See [Juju Terraform provider issue](https://github.com/juju/terraform-provider-juju/issues/344)