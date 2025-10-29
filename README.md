# Personal RAG System

A Retrieval-Augmented Generation (RAG) system for indexing and querying personal content from multiple sources.

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

### Ingest Documents

**From local directory**:
```bash
python ingest.py --source ~/Documents/notes --source-type local
```

**From Google Drive**:
```bash
# First time: will open browser for OAuth
python ingest.py --source-type gdrive
```

### Start the API Server

```bash
uvicorn api:app --reload --port 8000
```

### Start the Web UI

```bash
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## Project Structure

```
personal-rag/
├── src/
│   ├── config.py          # Configuration management
│   ├── chunking.py        # Document chunking logic
│   ├── embeddings.py      # Embedding interface
│   ├── ingestion.py       # Ingestion pipeline
│   ├── retrieval.py       # Query and retrieval
│   ├── models.py          # Pydantic models
│   └── connectors/        # Source connectors
│       ├── base.py        # Base connector interface
│       ├── local.py       # Local file system
│       └── gdrive.py      # Google Drive
├── api.py                 # FastAPI application
├── app.py                 # Streamlit UI
├── ingest.py             # CLI ingestion script
└── tests/                # Tests
```

## Documentation

- [DECISIONS.md](DECISIONS.md) - Architecture decision records
- [CLAUDE.md](CLAUDE.md) - Detailed documentation
- [HIGH-LEVEL-PLAN.md](HIGH-LEVEL-PLAN.md) - Implementation roadmap

## Google Drive Setup

To use Google Drive integration:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable Google Drive API
4. Create OAuth 2.0 credentials (Desktop application)
5. Download credentials as `credentials.json` in project root
6. First run will open browser for OAuth consent

## Development

### Run tests

```bash
uv pip install -e ".[dev]"
pytest
```

### Code formatting

```bash
black .
ruff check .
```

## License

Personal project - see repository for details.
