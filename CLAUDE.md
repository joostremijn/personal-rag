# Personal RAG System - Documentation

Quick reference for the Personal RAG system. See DECISIONS.md for architecture and HIGH-LEVEL-PLAN.md for roadmap.

## Current Status

**Phase**: MVP - Ingestion Complete ✅
- Local file ingestion: WORKING
- Google Drive ingestion: CODE READY (needs OAuth setup)
- Retrieval/Query: TODO
- FastAPI backend: TODO
- Streamlit UI: TODO

## Quick Start

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e .
cp .env.example .env  # Add OPENAI_API_KEY

# Ingest documents
python ingest.py --source ~/Documents/notes --source-type local

# View stats
python ingest.py --stats
```

## Architecture

```
User Query → [Embed] → [ChromaDB Search] → [GPT-4o Generate] → Response
Documents → [Chunk] → [Embed] → [ChromaDB Store]
```

**Tech Stack**: Python 3.11+, uv, LangChain, ChromaDB, OpenAI (text-embedding-3-small + gpt-4o), FastAPI, Streamlit

## Project Structure

```
src/
├── config.py          # Settings (env vars)
├── models.py          # Pydantic models
├── chunking.py        # Split docs (512 tokens, 50 overlap)
├── embeddings.py      # OpenAI embeddings
├── ingestion.py       # Pipeline: chunk → embed → store
├── retrieval.py       # Query ChromaDB (TODO)
└── connectors/
    ├── local.py       # Local files (.txt, .md, .pdf, .docx)
    └── gdrive.py      # Google Drive (needs credentials.json)

ingest.py              # CLI tool
api.py                 # FastAPI (TODO)
app.py                 # Streamlit UI (TODO)
```

## Configuration (.env)

```bash
OPENAI_API_KEY=sk-...
CHROMA_PERSIST_DIR=./data/chroma
CHUNK_SIZE=512
CHUNK_OVERLAP=50
TOP_K=5
```

## Ingestion Commands

```bash
# Local files
python ingest.py --source ~/notes --source-type local
python ingest.py --source file.pdf --source-type local

# Google Drive (needs credentials.json first)
python ingest.py --source-type gdrive --list-folders
python ingest.py --source-type gdrive --max-results 50
python ingest.py --source-type gdrive --folder-id "abc123"

# Management
python ingest.py --stats
python ingest.py --reset  # Clear collection
```

## Testing Results

**Last Test** (2025-10-29):
- ✅ Ingested 2 test docs (tests/fixtures/)
- ✅ Created 2 chunks, embedded, stored in ChromaDB
- ✅ Processing time: 0.47s
- ✅ Supported formats: .txt, .md, .pdf, .docx

## Google Drive Setup

1. [Google Cloud Console](https://console.cloud.google.com/) → Create project
2. Enable Google Drive API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download as `credentials.json` in project root
5. First run opens browser for OAuth consent

## Supported File Types

**Local**: .txt, .md, .pdf, .docx
**Google Drive**: Google Docs/Sheets, PDF, Word, text files

## Common Operations

**Re-index everything**:
```bash
rm -rf data/chroma/*
python ingest.py --source ~/notes --source-type local
```

**Troubleshooting**:
- ChromaDB errors → `rm -rf data/chroma/*`
- Import errors → `uv pip install -e .`
- Empty results → Check OPENAI_API_KEY in .env

## Key Concepts

**Chunking**: 512 tokens per chunk, 50 token overlap, recursive text splitting
**Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
**Storage**: ChromaDB with local persistence (./data/chroma/)
**Metadata**: Source, type, timestamps, file info tracked per chunk

## Next Steps

1. Build retrieval system (src/retrieval.py)
2. Create FastAPI endpoints (api.py)
3. Build Streamlit chat UI (app.py)
4. Test end-to-end RAG pipeline

## Performance

**MVP Scale**: 100-1000 docs, <5s queries
**Production Goal**: 200K docs (100 users × 2K), <3s queries
**Costs**: ~$0.01 for 1000 docs indexing, ~$4/day for 100 queries

## Development

**Code Style**: Type hints, PEP 8, Pydantic models, docstrings
**Testing**: pytest, fixtures in tests/fixtures/
**Git**: Don't commit .env or data/

## Resources

- [DECISIONS.md](DECISIONS.md) - Architecture decisions
- [HIGH-LEVEL-PLAN.md](HIGH-LEVEL-PLAN.md) - Full roadmap
- [LangChain Docs](https://python.langchain.com/)
- [ChromaDB Docs](https://docs.trychroma.com/)
