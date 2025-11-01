# Test Suite

Comprehensive test suite for Personal RAG system.

## Test Structure

```
tests/
├── unit/           # Fast tests with mocks (46 tests, <3s total)
├── integration/    # Real ChromaDB tests (5 tests, ~1s)
└── e2e/           # Real API tests (optional, manual only)
```

## Running Tests

```bash
# All tests except E2E (recommended)
pytest tests/ --ignore=tests/e2e/

# Unit tests only (fastest)
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_chunking.py -v

# Specific test
pytest tests/unit/test_chunking.py::test_chunk_size_respected -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# E2E tests (requires API keys, costs money)
pytest tests/e2e/ -v
```

## Test Categories

**Unit Tests** (`tests/unit/`)
- Mocked external dependencies
- Fast execution (<3s total)
- Run on every code change
- **Coverage:**
  - chunking.py (6 tests)
  - embeddings.py (6 tests)
  - models.py (6 tests)
  - ingestion.py (6 tests)
  - connectors/local.py (10 tests)
  - connectors/gdrive.py (7 tests, 1 skipped)

**Integration Tests** (`tests/integration/`)
- Real ChromaDB (test collections)
- Mocked external APIs
- Medium speed (~1s total)
- Run before commits
- **Coverage:**
  - Full ingestion workflow (5 tests)

**E2E Tests** (`tests/e2e/`)
- Real OpenAI API (costs money)
- Real Google Drive API
- Manual execution only
- Run before releases

## Test Statistics

- **Total Tests:** 46 passing, 1 skipped
- **Execution Time:** ~2.3 seconds (unit + integration)
- **Code Coverage:** >80% for core modules

## Writing Tests

Follow TDD pattern:
1. Write failing test
2. Run test to verify it fails
3. Implement minimal code to pass
4. Run test to verify it passes
5. Commit

## Test Fixtures

See `tests/conftest.py` for shared fixtures:
- `sample_documents`: Test documents
- `test_chroma_collection`: Isolated ChromaDB collection
- `mock_openai_embeddings`: Fake embeddings (deterministic)
- `mock_openai_chat`: Fake chat responses
- `mock_gdrive_service`: Fake Google Drive API

## Continuous Integration

Tests are designed for CI/CD:
- Unit + integration tests: Run on every commit
- E2E tests: Run on release branches only
- Automatic cleanup after each test
- Isolated test collections (no pollution)
