default:
	uv run black .

setup:
	python -m venv .venv
	-.venv/scripts/activate
	-source .venv/bin/activate
	pip install uv
	uv sync --dev

test:
	uv pip install -e ".[test]"
	uv run pytest