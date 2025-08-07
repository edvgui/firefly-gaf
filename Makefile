install:
	ls .venv || uv venv
	uv pip install -r requirements.dev.txt

lint:
	uv run flake8 --max-line-len 88 script.py
	uv run pyupgrade --py312-plus script.py

format:
	uv run isort script.py
	uv run black script.py
	$(MAKE) lint

build:
	podman build -t ghcr.io/edvgui/firefly-gaf:latest .
