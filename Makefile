.PHONY: lint format check test test-api test-pipeline test-js lint-py lint-js format-py format-js

# Run all linters
lint: lint-py lint-js

# Run all formatters
format: format-py format-js

# Check all formatting without modifying files
check: check-py check-js

# Run the deterministic local suites. These do not start Compose services,
# contact providers, or run the scheduler/bootstrap.
test: test-api test-pipeline test-js

test-api:
	uv run --extra api --group dev python -m pytest api/tests/ -v

test-pipeline:
	uv run --extra pipeline --group dev python -m pytest pipeline/tests/ -v

test-js:
	cd dashboard && bun run test && bun run typecheck

# Python linting with Ruff
lint-py:
	uv run --group dev ruff check api/ pipeline/ scripts/

# JavaScript/TypeScript linting with ESLint
lint-js:
	cd dashboard && bun run lint

# Python formatting with Ruff
format-py:
	uv run --group dev ruff format api/ pipeline/ scripts/

# JavaScript/TypeScript formatting with Prettier
format-js:
	cd dashboard && bun run format

# Check Python formatting (no modifications)
check-py:
	uv run --group dev ruff check api/ pipeline/ scripts/
	uv run --group dev ruff format --check api/ pipeline/ scripts/

# Check JS formatting (no modifications)
check-js:
	cd dashboard && bun run format:check && bun run lint && bun run typecheck
