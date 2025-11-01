# Personal RAG System

A Retrieval-Augmented Generation (RAG) system for indexing and querying personal documents from multiple sources using OpenAI embeddings and GPT-5.

**Status**: Phase 1 MVP Complete ✅

## Features

- 🔍 **Intelligent Search** - Vector similarity search with OpenAI embeddings
- 💬 **Chat Interface** - Interactive Streamlit UI for natural conversations
- 📚 **Multi-Source** - Index documents from local files and Google Drive
- 🤖 **GPT-5 Powered** - Context-aware answer generation with source citations
- ⚡ **Fast Retrieval** - ChromaDB vector database for efficient querying
- 🔄 **Flexible Modes** - "Accessed mode" for recently viewed files only
- 🌐 **REST API** - FastAPI backend for programmatic access

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- OpenAI API key

### Installation

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and setup**:
   ```bash
   cd personal-rag
   uv venv
   source .venv/bin/activate  # On macOS/Linux
   # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

4. **Create data directories**:
   ```bash
   mkdir -p data/chroma
   ```

## Usage

### 1. Ingest Documents

#### Local Files

```bash
# Ingest directory
python ingest.py --source ~/Documents/notes --source-type local

# Ingest single file
python ingest.py --source ~/file.pdf --source-type local

# View collection stats
python ingest.py --stats
```

#### Google Drive

**First time setup**: See [GOOGLE-OAUTH.md](GOOGLE-OAUTH.md) for OAuth configuration.

```bash
# List your Google Drive folders
python ingest.py --source-type gdrive --list-folders

# Ingest recently accessed files (last 2 years)
python ingest.py --source-type gdrive --mode=accessed --max-results 100

# Ingest recently accessed (last 6 months)
python ingest.py --source-type gdrive --mode=accessed --days-back 180

# Ingest all Drive files
python ingest.py --source-type gdrive --mode=drive --max-results 50

# Dry run (preview without ingesting)
python ingest.py --source-type gdrive --mode=accessed --dry-run
```

**Supported file types:**
- Google Docs, Google Sheets
- PDF, DOCX, TXT, MD

### 2. Query Your Documents

#### Option A: Streamlit Chat UI (Recommended)

```bash
streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

**Features:**
- 💬 Chat interface with conversation history
- 📚 Expandable source display with metadata
- ⚙️ Configurable settings (number of sources, filters)
- 🔗 Direct links to source documents

#### Option B: CLI Query Tool

```bash
# Simple query
python query.py "what are my notes about Python?"

# With options
python query.py "machine learning projects" --top-k 10 --show-scores

# Filter by source type
python query.py "meeting notes" --source-type gdrive

# View stats
python query.py --stats
```

#### Option C: REST API

```bash
# Start API server
python api.py

# Then in another terminal
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "your question", "top_k": 5}'
```

**API Endpoints:**
- `GET /health` - Health check with collection stats
- `POST /query` - Query documents and get AI-generated answer
- `GET /stats` - Collection statistics

## Configuration

### Environment Variables (.env)

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional (defaults shown)
LLM_MODEL=gpt-5
LLM_TEMPERATURE=0.7
EMBEDDING_MODEL=text-embedding-3-small
CHUNK_SIZE=512
CHUNK_OVERLAP=50
TOP_K=5
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_COLLECTION_NAME=personal_docs
```

See [CLAUDE.md](CLAUDE.md) for complete configuration reference.

## Project Structure

```
personal-rag/
├── src/
│   ├── config.py          # Configuration management
│   ├── models.py          # Pydantic data models
│   ├── chunking.py        # Document splitting (512 tokens/chunk)
│   ├── embeddings.py      # OpenAI embedding interface
│   ├── ingestion.py       # Ingestion pipeline
│   ├── retrieval.py       # ChromaDB query interface
│   └── connectors/        # Source connectors
│       ├── base.py        # Abstract connector
│       ├── local.py       # Local files (.txt, .md, .pdf, .docx)
│       └── gdrive.py      # Google Drive with OAuth
├── ingest.py              # CLI ingestion tool
├── query.py               # CLI query tool
├── api.py                 # FastAPI backend
├── app.py                 # Streamlit chat UI
├── data/                  # Data storage (gitignored)
│   └── chroma/            # ChromaDB vector database
├── tests/                 # Test files
│   └── fixtures/          # Test documents
├── .env                   # Configuration (gitignored)
├── credentials.json       # Google OAuth credentials (gitignored)
└── token.json            # Google access token (gitignored)
```

## Common Operations

### Update Google Drive Documents

```bash
# Incremental update (only process new/changed files)
python ingest.py --source-type gdrive --mode=accessed --max-results 100
```

### Check What's Indexed

```bash
# Via ingestion tool
python ingest.py --stats

# Via query tool
python query.py --stats
```

### Reset Collection

```bash
# Clear everything and start fresh
python ingest.py --source ~/notes --source-type local --reset
```

### Test Retrieval

```bash
# Simple test
python query.py "test" --show-scores

# Check for specific document
python query.py "unique text from document" --top-k 1
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Complete reference guide with all commands
- **[GOOGLE-OAUTH.md](GOOGLE-OAUTH.md)** - Step-by-step Google Drive setup (⭐ Start here for Drive)
- **[PLAN-REMAINDER.md](PLAN-REMAINDER.md)** - Next implementation steps (Phase 2+)
- **[DECISIONS.md](DECISIONS.md)** - Architecture decisions and rationale
- **[HIGH-LEVEL-PLAN.md](HIGH-LEVEL-PLAN.md)** - Full project roadmap

## Google Drive Setup

To use Google Drive integration:

1. See the comprehensive guide: **[GOOGLE-OAUTH.md](GOOGLE-OAUTH.md)**
2. Quick summary:
   - Create Google Cloud project
   - Enable Google Drive API
   - Configure OAuth consent screen
   - Create Desktop app credentials
   - Download `credentials.json`
   - Run ingestion (browser opens for auth)

**Alternative (simpler):** Use [Google Drive Desktop](https://www.google.com/drive/download/) and ingest the synced local folder:
```bash
python ingest.py --source ~/Google\ Drive/My\ Drive --source-type local
```

## Troubleshooting

### Installation Issues
- **ChromaDB errors**: `rm -rf data/chroma/*` and re-run
- **Import errors**: Reinstall with `uv pip install -e .`
- **Empty results**: Check `OPENAI_API_KEY` in `.env`

### Google Drive Issues
- **Token expired**: Delete `token.json` and re-run ingestion
- **OAuth errors**: Verify `credentials.json` format, check [GOOGLE-OAUTH.md](GOOGLE-OAUTH.md)
- **No files found**: Check API enabled in Google Cloud Console

### Query Issues
- **No results**: Try `--min-score 0` or verify documents are ingested
- **Slow responses**: GPT-5 takes 30-80 seconds (expected)
- **Wrong results**: Adjust `--top-k` or tune chunk size in `.env`

### Streamlit Issues
- **Port in use**: Kill with `pkill -f streamlit` and restart
- **Not loading**: Check logs, verify OpenAI API key
- **Empty collection**: Run ingestion first with `python ingest.py --stats`

## Architecture

```
User Query → Embed (OpenAI) → Vector Search (ChromaDB) → GPT-5 Generate → Answer
Documents → Chunk (512 tokens) → Embed → Store (ChromaDB)
```

**Tech Stack:**
- **Python 3.11+** with uv package manager
- **LangChain** for document processing
- **ChromaDB** for vector storage (local persistence)
- **OpenAI** for embeddings (text-embedding-3-small) and generation (GPT-5)
- **FastAPI** for REST API
- **Streamlit** for chat UI

## Performance

- **Current**: 76 chunks indexed (test documents)
- **Target**: 100-1000 documents for personal use
- **Query Time**: 30-80 seconds (GPT-5 generation time)
- **Costs**: ~$0.01 per 1000 docs indexed, ~$0.01-0.02 per query

## Development

### Running Tests

**IMPORTANT**: Always run tests before merging changes. Never skip or delete tests without user approval.

```bash
# Activate environment first
source .venv/bin/activate

# Run all tests (recommended before commits)
pytest tests/ --ignore=tests/e2e/

# Fast unit tests only (<3s)
pytest tests/unit/ -v

# Integration tests (with real ChromaDB)
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_chunking.py -v

# With coverage report
pytest tests/ --ignore=tests/e2e/ --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

**Test Suite Structure:**
```
tests/
├── unit/                # Fast tests with mocked dependencies (41 tests, <3s)
│   ├── test_chunking.py
│   ├── test_embeddings.py
│   ├── test_models.py
│   ├── test_ingestion.py
│   └── connectors/
│       ├── test_local.py
│       └── test_gdrive.py
├── integration/         # Real ChromaDB tests (5 tests, ~1s)
│   └── test_ingestion.py
├── e2e/                 # Real API tests (manual only, costs money)
└── conftest.py          # Shared fixtures
```

**Current Test Statistics:**
- **46 passing, 1 skipped**
- **Execution Time**: ~2.3 seconds (unit + integration)
- **Code Coverage**: >80% for core modules

**What Tests Cover:**
- Document chunking with token limits and overlap
- Embedding generation and batch processing
- ChromaDB ingestion and retrieval workflows
- Local file connector (permissions, encoding, symlinks)
- Google Drive connector (OAuth, MIME types, file listing)
- Real failure scenarios (not just happy paths)

See **[tests/README.md](tests/README.md)** for complete test documentation.

### Test Hygiene Rules

**Before Committing:**
1. Run `pytest tests/ --ignore=tests/e2e/`
2. Verify all tests pass (46 passed, 1 skipped expected)
3. If tests fail: fix the code or ask for guidance
4. Never skip/delete tests without approval

**Requires User Approval:**
- Skipping tests (`@pytest.mark.skip`)
- Deleting tests
- Changing assertions to make tests pass
- Reducing test coverage

**Rationale**: Tests are the safety net preventing regressions.

### Code Style

```bash
# Format code
black .

# Lint
ruff check .
```

## Next Steps

See [PLAN-REMAINDER.md](PLAN-REMAINDER.md) for Phase 2 priorities:

1. **Incremental ingestion** - Only process new/changed files
2. **Scheduled ingestion** - Automated updates with cron/APScheduler
3. **Better error handling** - Improved logging and notifications
4. **Production deployment** - Docker, Hetzner server, authentication

## Contributing

This is a personal project. Feel free to fork and adapt for your own use!

## Resources

- [LangChain Documentation](https://python.langchain.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [OpenAI API Documentation](https://platform.openai.com/docs)

## License

Personal project - see repository for details.

---

**Built with Claude Code** 🤖
