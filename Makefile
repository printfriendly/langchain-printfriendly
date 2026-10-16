.PHONY: all format lint test integration_test live_test build

all: format lint test

format:
	uv run --group lint ruff format .
	uv run --group lint ruff check --fix .

lint:
	uv run --group lint ruff format --check .
	uv run --group lint ruff check .
	uv run --group lint --group test mypy langchain_printfriendly tests
	uv run --group lint codespell .

# Unit tests: no network. pytest-socket fails any test that tries to open one.
test:
	uv run --group test pytest --disable-socket --allow-unix-socket tests/unit_tests

# LangChain's standard integration suite, against a mocked API (spends nothing).
integration_test:
	uv run --group test pytest tests/integration_tests --ignore=tests/integration_tests/test_live.py

# Real API. Needs PRINTFRIENDLY_API_KEY. Reads two pages: two documents of the plan.
live_test:
	uv run --group test pytest tests/integration_tests/test_live.py

build:
	uv build
