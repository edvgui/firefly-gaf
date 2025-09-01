SHELL := /bin/bash

# Env var inputs for container image builds
# REGISTRY: The registry to which the build image should be pushed to.
# IMAGE: The name of the image to build and publish in the afore mentioned registry.
# PLATFORM: The platform for which the image should be built
REGISTRY ?= docker.io
IMAGE ?= firefly/gaf
PLATFORM ?= linux/amd64,linux/arm64,linux/386,linux/arm/v7,linux/riscv64

install:
	ls .venv || uv venv
	uv pip install -r requirements.dev.txt
	uv export --script script.py | uv pip install --requirements -

lint:
	uv run flake8 --max-line-len 88 script.py
	uv run pyupgrade --py312-plus script.py

format:
	uv run isort script.py
	uv run black script.py
	$(MAKE) lint

build:
	docker buildx build \
	$(if $(PUSH),--push) \
	-t ${REGISTRY}/${IMAGE}:latest \
	--platform ${PLATFORM} \
	-f Containerfile \
	.
