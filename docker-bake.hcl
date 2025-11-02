# Docker Bake configuration for building application images
# https://docs.docker.com/build/bake/

target "app" {
  context    = "./app"
  dockerfile = "./Dockerfile"
  tags       = ["dagster-taskiq-demo:latest"]
  platforms  = ["linux/amd64"]
}
