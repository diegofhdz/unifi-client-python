.PHONY: help install install-dev test coverage lint format type-check clean build publish-test publish

help:
	@echo "Available commands:"
	@echo "  install       - Install package"
	@echo "  install-dev   - Install package with dev dependencies"
	@echo "  test          - Run tests"
	@echo "  coverage      - Run tests with coverage report"
	@echo "  lint          - Run flake8 linter"
	@echo "  format        - Format code with black"
	@echo "  type-check    - Run mypy type checker"
	@echo "  clean         - Remove build artifacts"
	@echo "  build         - Build package"
	@echo "  publish-test  - Publish to Test PyPI"
	@echo "  publish       - Publish to PyPI"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest -v

coverage:
	pytest --cov=unifi_client --cov-report=html --cov-report=term-missing

lint:
	flake8 src/ tests/

format:
	black src/ tests/

format-check:
	black --check src/ tests/

type-check:
	mypy src/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

build: clean
	python -m build

publish-test: build
	twine upload --repository testpypi dist/*

publish: build
	twine upload dist/*

all: format lint type-check test
