// Docker Bake configuration for building application images
// https://docs.docker.com/build/bake/

variable "PROJECT_NAME" {
  default = "dagster-taskiq-demo"
}

variable "ENVIRONMENT" {
  default = "local"
}

variable "IMAGE_TAG" {
  default = "latest"
}

variable "PLATFORM" {
  default = "linux/amd64"
}

// Build the application image
target "app" {
  context    = "./app"
  dockerfile = "./Dockerfile"
  tags       = ["${PROJECT_NAME}-${ENVIRONMENT}:${IMAGE_TAG}"]
  platforms  = [PLATFORM]
}
