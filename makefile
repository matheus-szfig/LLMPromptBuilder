default:
	python -m venv .venv
	-.venv/scripts/activate
	-source .venv/bin/activate
	pip install uv
	uv sync