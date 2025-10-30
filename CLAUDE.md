# Personal RAG System - Documentation

Quick reference for the Personal RAG system. See DECISIONS.md for architecture and HIGH-LEVEL-PLAN.md for roadmap.

## Current Status

**Phase 1 MVP**: COMPLETE ✅
- ✅ Local file ingestion: WORKING
- ✅ Google Drive ingestion: WORKING (OAuth setup required)
- ✅ Retrieval/Query: WORKING
- ✅ FastAPI backend: WORKING
- ✅ Streamlit UI: WORKING

## Quick Start

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e .
cp .env.example .env  # Add OPENAI_API_KEY

# Google Drive OAuth (one-time setup)
# See GOOGLE-OAUTH.md for detailed instructions

# Ingest documents
python ingest.py --source-type gdrive --mode=accessed --max-results 100

# Query via CLI
python query.py "what are my notes about Python?"

# Start chat UI
streamlit run app.py
# Open http://localhost:8501

# Start API (optional)
python api.py
# API at http://localhost:8000
```

## Architecture

```
User Query → [Embed] → [ChromaDB Search] → [GPT-5 Generate] → Response
Documents → [Chunk] → [Embed] → [ChromaDB Store]
```

**Tech Stack**: Python 3.11+, uv, LangChain, ChromaDB, OpenAI (text-embedding-3-small + GPT-5), FastAPI, Streamlit

## Project Structure

```
src/
├── config.py          # Settings (env vars)
├── models.py          # Pydantic models
├── chunking.py        # Split docs (512 tokens, 50 overlap)
├── embeddings.py      # OpenAI embeddings
├── ingestion.py       # Pipeline: chunk → embed → store
├── retrieval.py       # Query ChromaDB
└── connectors/
    ├── base.py        # Abstract connector
    ├── local.py       # Local files (.txt, .md, .pdf, .docx)
    └── gdrive.py      # Google Drive

ingest.py              # CLI tool for ingestion
query.py               # CLI tool for querying
api.py                 # FastAPI backend
app.py                 # Streamlit UI
```

## Configuration (.env)

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
API_HOST=0.0.0.0
API_PORT=8000
```

## Ingestion

### Local Files

```bash
# Ingest directory
python ingest.py --source ~/Documents/notes --source-type local

# Ingest single file
python ingest.py --source ~/file.pdf --source-type local

# With reset (clear collection first)
python ingest.py --source ~/notes --source-type local --reset
```

### Google Drive

**First time setup**: See GOOGLE-OAUTH.md for OAuth configuration.

```bash
# List folders (useful for finding folder IDs)
python ingest.py --source-type gdrive --list-folders

# Ingest recently accessed files (default: last 2 years)
python ingest.py --source-type gdrive --mode=accessed --max-results 100

# Ingest recently accessed (last 6 months)
python ingest.py --source-type gdrive --mode=accessed --days-back 180

# Ingest all files in Drive
python ingest.py --source-type gdrive --mode=drive --max-results 50

# Ingest specific folder
python ingest.py --source-type gdrive --folder-id "abc123xyz"

# Dry run (preview without ingesting)
python ingest.py --source-type gdrive --mode=accessed --dry-run --max-results 10
```

### Management

```bash
# View collection statistics
python ingest.py --stats

# Reset collection (delete all documents)
python ingest.py --source ~/notes --source-type local --reset
```

## Querying

### CLI Query Tool

```bash
# Simple query
python query.py "what are my notes about Python?"

# With custom top_k
python query.py "machine learning projects" --top-k 10

# Filter by source type
python query.py "meeting notes" --source-type gdrive

# Show similarity scores
python query.py "vision pro apps" --show-scores

# Set minimum score threshold
python query.py "test" --min-score 0.4

# Collection stats
python query.py --stats
```

### Streamlit Chat UI

```bash
# Start Streamlit
streamlit run app.py

# Then open http://localhost:8501 in browser
```

**Features:**
- 💬 Chat interface with history
- 🔍 Real-time search and answer generation
- 📚 Expandable source display with metadata
- ⚙️ Settings: adjust top_k, filter by source type
- 🗑️ Clear chat history

**Sidebar Settings:**
- Number of sources (1-10 slider)
- Filter by source type (local/gdrive)
- Collection statistics
- Model information

### FastAPI Backend

```bash
# Start API server
python api.py

# Then API available at http://localhost:8000
```

**Endpoints:**
```bash
# Health check
curl http://localhost:8000/health

# Query
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "your question", "top_k": 5}'

# Stats
curl http://localhost:8000/stats
```

## Supported File Types

**Local Files:**
- Plain text: `.txt`, `.md`
- Documents: `.pdf`, `.docx`

**Google Drive:**
- Google Docs (exported as text)
- Google Sheets (exported as CSV)
- PDFs, Word documents, text files

## Common Operations

### Re-index Everything
```bash
rm -rf data/chroma/*
python ingest.py --source ~/notes --source-type local
```

### Update Google Drive Documents
```bash
# Incremental update (only new/changed files)
python ingest.py --source-type gdrive --mode=accessed --max-results 100
```

### Check What's Indexed
```bash
# View stats
python ingest.py --stats

# Or via query tool
python query.py --stats
```

### Test Retrieval
```bash
# Simple test query
python query.py "test" --show-scores

# Check if specific document is indexed
python query.py "search for unique text from document" --top-k 1
```

## Troubleshooting

### Installation Issues
- ChromaDB errors → `rm -rf data/chroma/*`
- Import errors → `uv pip install -e .`
- Empty results → Check `OPENAI_API_KEY` in `.env`

### Google Drive Issues
- Token expired → `rm token.json` and re-run ingestion
- OAuth errors → Check credentials.json, see GOOGLE-OAUTH.md
- No folders found → Verify API enabled in Google Cloud Console

### Query Issues
- No results → Lower `--min-score` or check if documents are ingested
- Slow responses → Normal for GPT-5 (30-80 seconds)
- Wrong results → Try adjusting `TOP_K` or chunk size

### Streamlit Issues
- Port in use → `pkill -f streamlit` and restart
- Not loading → Check logs, verify OpenAI API key
- Empty collection → Run ingestion first

## Key Concepts

**Chunking**: 512 tokens per chunk, 50 token overlap, recursive text splitting
**Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
**LLM**: GPT-5 for answer generation
**Storage**: ChromaDB with local persistence (./data/chroma/)
**Metadata**: Source, type, timestamps, file info tracked per chunk

## Performance

**Current Scale**: 76 chunks (test data)
**Target MVP Scale**: 100-1000 docs, <5s queries (note: GPT-5 takes 30-80s)
**Production Goal**: 200K docs (100 users × 2K), <3s queries
**Costs**:
- Indexing: ~$0.01 per 1000 docs
- Queries: ~$0.01-0.02 per query (GPT-5)

## Development

**Code Style**: Type hints, PEP 8, Pydantic models, docstrings
**Testing**: pytest, fixtures in tests/fixtures/
**Git**: Don't commit .env, data/, credentials.json, token.json

## Next Steps

See PLAN-REMAINDER.md for Phase 2 priorities:
1. Incremental ingestion (avoid re-processing unchanged files)
2. Scheduled ingestion (automation with cron/APScheduler)
3. Better error handling and logging
4. Comprehensive README documentation

## Resources

- [PLAN-REMAINDER.md](PLAN-REMAINDER.md) - Next implementation steps
- [DECISIONS.md](DECISIONS.md) - Architecture decisions
- [HIGH-LEVEL-PLAN.md](HIGH-LEVEL-PLAN.md) - Full roadmap
- [GOOGLE-OAUTH.md](GOOGLE-OAUTH.md) - Google Drive setup
- [LangChain Docs](https://python.langchain.com/)
- [ChromaDB Docs](https://docs.trychroma.com/)
