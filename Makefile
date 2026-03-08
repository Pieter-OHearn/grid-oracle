.PHONY: lint format check lint-py lint-js format-py format-js

# Run all linters
lint: lint-py lint-js

# Run all formatters
format: format-py format-js

# Check all formatting without modifying files
check: check-py check-js

# Python linting with Ruff
lint-py:
	ruff check api/ pipeline/

# JavaScript/TypeScript linting with ESLint
lint-js:
	cd dashboard && npm run lint

# Python formatting with Ruff
format-py:
	ruff format api/ pipeline/

# JavaScript/TypeScript formatting with Prettier
format-js:
	cd dashboard && npm run format

# Check Python formatting (no modifications)
check-py:
	ruff check api/ pipeline/
	ruff format --check api/ pipeline/

# Check JS formatting (no modifications)
check-js:
	cd dashboard && npm run format:check && npm run lint
