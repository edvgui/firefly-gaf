# Build stage: the -dev variant has a shell; uv is added for dependency handling
FROM cgr.dev/chainguard/python:latest-dev AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

COPY script.py script.py.lock /

USER root
RUN <<EOF
set -e

# Create a venv holding the script's dependencies, pinned by the lock file,
# to ensure that the image is always built with the same dependencies
uv venv /venv
uv export --script /script.py --frozen | uv pip install --python /venv --requirements -

# Make sure the script can run with this environment
/venv/bin/python /script.py --help
EOF

# Runtime stage: distroless python (no shell, no package manager, nonroot user)
FROM cgr.dev/chainguard/python:latest
COPY --from=build /venv /venv
COPY --from=build /script.py /script.py

ENTRYPOINT ["/venv/bin/python", "/script.py"]
