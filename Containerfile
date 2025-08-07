# Install uv
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN --mount=type=bind,target=/tmp/gaf,z <<EOF
set -e

# Copy the script to the root of the image
cp /tmp/gaf/script.py /script.py

# Copy the lock file, to ensure that the image is always build with
# the same dependencies
cp /tmp/gaf/script.py.lock /script.py.lock

# Execute the script a first time to cache all the dependencies
/script.py --help
EOF

ENTRYPOINT ["/script.py"]
