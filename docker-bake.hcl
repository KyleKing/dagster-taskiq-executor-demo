# Docker Bake configuration for building application images
# https://docs.docker.com/build/bake/

target "dagster-taskiq-demo" {
  context    = "./dagster-taskiq-demo"
  dockerfile = "./Dockerfile"
  contexts   = {
    "dagster-taskiq" = "./dagster-taskiq"
  }
  tags       = ["dagster-taskiq-demo:latest"]
  platforms  = ["linux/amd64"]
}
