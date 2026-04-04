.PHONY: build start stop restart start-cli-list start-cli-scan start-cli-add

COMPOSE_FILE := docker-compose.yml

-include .env

DC := docker-compose -f $(COMPOSE_FILE)


build:
	$(DC) build

.PHONY: build start stop restart logs ps start-cli-list start-cli-scan start-cli-add cli-list cli-scan cli-add cli-summary web-local web-local-dev test test-unit test-integration

start: ## Start the services in detached mode
	$(DC) up -d

stop: ## Stop and remove containers, networks
	$(DC) down

restart: stop build start

logs: ## Follow log output from containers
	$(DC) logs -f

ps: ## List containers
	$(DC) ps

# --- Additional helper target to verify the service is up ---
smoke: start
	@echo "Waiting for service to become healthy..."
	@for i in $$(seq 1 30); do \
		if docker inspect --format='{{json .State.Health.Status}}' junit-dashboard 2>/dev/null | grep -q healthy; then \
			echo "Service is healthy"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Service did not become healthy in time"; \
	exit 1

# --- CLI Commands ---
start-cli-list: ## List all projects via CLI
	@if command -v python3 >/dev/null 2>&1; then \
		echo "Running CLI locally..."; \
		python3 run_cli.py list-projects; \
	else \
		echo "Running CLI in container..."; \
		$(DC) exec junit-dashboard python3 run_cli.py list-projects; \
	fi

start-cli-scan: ## Scan for new test files via CLI
	@if command -v python3 >/dev/null 2>&1; then \
		echo "Running CLI locally..."; \
		python3 run_cli.py scan; \
	else \
		echo "Running CLI in container..."; \
		$(DC) exec junit-dashboard python3 run_cli.py scan; \
	fi

start-cli-add: ## Add a new project via CLI (usage: make start-cli-add NAME="Project Name" DIR="/path/to/tests")
	@if [ -z "$(NAME)" ] || [ -z "$(DIR)" ]; then \
		echo "Usage: make start-cli-add NAME=\"Project Name\" DIR=\"/path/to/tests\""; \
		echo "Example: make start-cli-add NAME=\"My Tests\" DIR=\"/workspace/results\""; \
		exit 1; \
	fi
	@if command -v python3 >/dev/null 2>&1; then \
		echo "Running CLI locally..."; \
		python3 run_cli.py add-project "$(NAME)" "$(DIR)"; \
	else \
		echo "Running CLI in container..."; \
		$(DC) exec junit-dashboard python3 run_cli.py add-project "$(NAME)" "$(DIR)"; \
	fi

# --- Native CLI Commands (without Docker) ---
cli-list: ## List projects using local Python
	python3 run_cli.py list-projects

cli-scan: ## Scan for new files using local Python
	python3 run_cli.py scan

cli-add: ## Add project using local Python (usage: make cli-add NAME="Project" DIR="/path")
	@if [ -z "$(NAME)" ] || [ -z "$(DIR)" ]; then \
		echo "Usage: make cli-add NAME=\"Project Name\" DIR=\"/path/to/tests\""; \
		exit 1; \
	fi
	python3 run_cli.py add-project "$(NAME)" "$(DIR)"

cli-summary: ## Show project summary using local Python (usage: make cli-summary ID=1)
	@if [ -z "$(ID)" ]; then \
		echo "Usage: make cli-summary ID=1"; \
		exit 1; \
	fi
	python3 run_cli.py project-summary $(ID)

# --- Web Server Commands ---
web-local: ## Run web server locally (non-Docker)
	python3 run_web.py --config config.yaml

web-local-dev: ## Run web server locally in debug mode
	python3 run_web.py --config config.yaml --debug

# --- Test Commands ---
test: ## Run all tests
	python3 run_tests.py

test-unit: ## Run only unit tests (core modules)
	python3 -m unittest discover -s tests -p "test_core_*.py" -v

test-integration: ## Run only integration tests (web interface)
	python3 -m unittest discover -s tests -p "test_web_*.py" -v

test-models: ## Run only model tests
	python3 -m unittest tests.test_core_models -v

test-parser: ## Run only parser tests
	python3 -m unittest tests.test_core_parser -v

test-service: ## Run only service tests
	python3 -m unittest tests.test_core_service -v

test-web: ## Run only web tests
	python3 -m unittest discover -s tests -p "test_web_*.py" -v

test-coverage: ## Run tests with coverage report (requires coverage.py)
	@if command -v coverage >/dev/null 2>&1; then \
		coverage run -m pytest tests/ -v; \
		coverage report -m; \
		coverage html; \
	else \
		echo "Coverage not available. Install with: pip install coverage"; \
		python3 run_tests.py; \
	fi

