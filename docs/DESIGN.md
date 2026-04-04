# Test Report Viewer - Design Documentation

## Architecture Overview

The application follows a modular architecture with clear separation between core business logic and interface adapters.

### Core Layer
Business logic, models, and services that are independent of any specific interface:

- `test_report_viewer/core/models.py` - SQLAlchemy data models (Project, TestRun, Test, TestResult, Status)
- `test_report_viewer/core/service.py` - Central business logic service (TestReportService)
- `test_report_viewer/core/parser.py` - JUnit XML parsing functionality
- `test_report_viewer/core/scanner.py` - Project scanning and file discovery

### Adapters Layer
Interface implementations that use the core services:

- `test_report_viewer/adapters/web/` - Flask web interface
  - `app.py`
  - `templates/`
  - `static/`

- `test_report_viewer/adapters/cli/` - Click command-line interface
  - `commands.py`

### Entry Points
Following are the entrypoints for the application:

- `run_web.py`
- `run_cli.py`

## Design Principles

### Dependency Direction
- Core layer has no dependencies on adapter layers
- Adapters depend on and use core services
- Both web and CLI interfaces use the same business logic service

### Service Layer Pattern
- `TestReportService` centralizes all business operations
- Database session management handled at service level
- Both interfaces delegate to service methods rather than accessing models directly

### Configuration
- Environment variables for runtime configuration (`PORT`, `DATABASE_URL`)
- YAML configuration files for application settings
- Docker environment support with .env files

## Database Design

### Models
- `Project` - Test project configuration (name, identifier, output directory)
- `TestRun` - Individual test execution (timestamp, file, totals)
- `Test` - Test case definitions (name, project association)
- `TestResult` - Individual test results (status, time, details)
- `Status` - Enumeration for test outcomes (passed, failed, error, skipped)

### Relationships
- Projects have many TestRuns and Tests
- TestRuns have many TestResults
- Tests have many TestResults (across different runs)
- TestResults link specific Tests to specific TestRuns

## Testing Strategy

### Test Organization
- `tests/test_core_models.py` - Unit tests for data models and relationships
- `tests/test_core_parser.py` - Unit tests for JUnit XML parsing logic
- `tests/test_core_service.py` - Unit tests for business logic service
- `tests/test_web_basic.py` - Basic web interface integration tests

### Test Isolation
- Each test uses temporary SQLite database
- Database session lifecycle managed per test
- No shared state between test methods

