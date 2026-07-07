SHELL := /bin/bash

# Env var inputs for container image builds
# REGISTRY: The registry to which the build image should be pushed to.
# IMAGE: The name of the image to build and publish in the afore mentioned registry.
# PLATFORM: The platform for which the image should be built
# COMMIT: The commit of this project for which the cli is being built, for reference in the tool's "version" command.
#         Default to git's HEAD
# METADATA_FILE: When set, write build metadata (including the image digest) to this file
# SOURCE: The url of the source repository of the image, displayed by registries
# DESCRIPTION: A one-line description of the image, displayed by registries
REGISTRY ?= docker.io
IMAGE ?= firefly/gaf
PLATFORM ?= linux/amd64,linux/arm64
COMMIT ?= $(shell git rev-parse --verify HEAD)
SOURCE ?= https://github.com/edvgui/firefly-gaf
DESCRIPTION ?= Firefly III helper that creates rules to sort transactions out of generic payment-provider accounts

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

build-multi-platform:
	docker buildx build \
	$(if $(PUSH),--push) \
	$(if $(METADATA_FILE),--metadata-file ${METADATA_FILE}) \
	-t ${REGISTRY}/${IMAGE}:latest \
	-t ${REGISTRY}/${IMAGE}:${COMMIT} \
	--label "org.opencontainers.image.source=${SOURCE}" \
	--label "org.opencontainers.image.description=${DESCRIPTION}" \
	--annotation "index,manifest:org.opencontainers.image.source=${SOURCE}" \
	--annotation "index,manifest:org.opencontainers.image.description=${DESCRIPTION}" \
	--platform ${PLATFORM} \
	-f Containerfile \
	.

build:
	docker build -t ${REGISTRY}/${IMAGE}:latest -f Containerfile .
