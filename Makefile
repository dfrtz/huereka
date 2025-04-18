PROJECT_ROOT := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
PYTHON_BIN := python3.12
NAME := huereka


##### Initial Development Setups and Configurations #####

# Set up initial environment for development.
.PHONY: setup
setup:
	ln -sfnv $(PROJECT_ROOT).hooks/pre-push $(PROJECT_ROOT).git/hooks/pre-push

# Create python virtual environment for development/testing.
.PHONY: venv
venv:
	$(PYTHON_BIN) -m venv $(PROJECT_ROOT).venv && \
	ln -sfnv $(PROJECT_ROOT).venv/bin/activate $(PROJECT_ROOT)activate && \
	source $(PROJECT_ROOT)activate && \
	pip install -r requirements-dev.txt -r requirements.txt && \
	echo $(PROJECT_ROOT) > $(PROJECT_ROOT).venv/lib/$(PYTHON_BIN)/site-packages/$(NAME).pth

# Clean the python virtual environment.
.PHONY: clean-venv
clean-venv:
	rm -r $(PROJECT_ROOT)activate $(PROJECT_ROOT).venv


##### Quality Assurance #####

# Check source code format for consistent patterns.
.PHONY: format
format:
	@echo Running code format checks: black/ruff
	@ruff format --check --diff $(PROJECT_ROOT) && echo "🏆 Code format good to go!" || \
		(echo "💔 Please run formatter to ensure code consistency and quality:\nruff format $(PROJECT_ROOT)"; exit 1)

# Check for common lint/complexity/style issues.
# Ruff is used for isort, pycodestyle, pydocstyle. Pylint is used separately for greater coverage.
.PHONY: lint
lint:
	@echo Running code and documentation style checks: isort, pycodestyle, pydocstyle
	@ruff check $(PROJECT_ROOT) && echo "🏆 Code/Doc style good to go!" || \
		(echo "💔 Please resolve all style warnings to ensure readability, scalability, and maintainability:\nruff check --fix $(PROJECT_ROOT)"; exit 1)
	@echo Running code quality checks: pylint
	@pylint $(NAME) && echo "🏆 Code quality good to go!" || \
		(echo "💔 Please resolve all code quality warnings to ensure scalability and maintainability."; exit 1)

# Check typehints for static typing best practices.
.PHONY: typing
typing:
	@echo Running code typechecks: mypy
	@mypy $(PROJECT_ROOT) && echo "🏆 Code typechecks good to go!" || \
		(echo "💔 Please resolve all typecheck warnings to ensure readability and stability."; exit 1)

# Check for common security issues/best practices.
.PHONY: security
security:
	@echo Running security scans: bandit
	@bandit -r -c=$(PROJECT_ROOT)pyproject.toml $(PROJECT_ROOT) && echo "🏆 Code security good to go!" || \
		(echo "💔 Please resolve all security warnings to ensure user and developer safety."; exit 1)

# Check full code quality suite (minus unit tests) against source.
# Does not enforce unit tests to simplify pushes, unit tests should be automated via pipelines with standardized env.
# Ensure format is first, as it will often solve many style and lint failures.
.PHONY: qa
qa: format lint typing security

# Run basic unit tests.
.PHONY: test
test:
	@pytest -n auto $(PROJECT_ROOT) --cov && echo "🏆 Tests good to go!" || \
		(echo "💔 Please resolve all test failures to ensure stability and quality."; exit 1)


##### Builds #####

# Package the library into a pip installable.
.PHONY: wheel
wheel:
	python -m build

# Clean the packages from all builds.
.PHONY: clean
clean:
	rm -r $(PROJECT_ROOT)dist $(PROJECT_ROOT)$(NAME).egg-info
