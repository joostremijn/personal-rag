# Personal RAG - Remaining Implementation Plan

**Last Updated:** 2025-10-30
**Current Status:** Phase 1 MVP Complete ✅

## What's Been Completed

### Phase 1 MVP ✅
All core functionality is working:

1. **Ingestion Pipeline** ✅
   - Local file ingestion (PDF, DOCX, MD, TXT)
   - Google Drive ingestion with OAuth2
   - Pagination support for large Drive accounts
   - "Accessed mode" for recently viewed files (last 730 days)
   - Dry-run preview (24x faster with metadata-only mode)
   - CLI tool: `python ingest.py`

2. **Retrieval System** ✅
   - ChromaDB vector search with OpenAI embeddings
   - Source type filtering
   - Query CLI: `python query.py "question"`

3. **FastAPI Backend** ✅
   - REST API at http://localhost:8000
   - Endpoints: `/health`, `/query`, `/stats`
   - GPT-5 integration for answer generation
   - Source citations in answers

4. **Streamlit UI** ✅
   - Interactive chat interface at http://localhost:8501
   - Chat history with session state
   - Expandable source display
   - Configurable settings (top_k, source filters)

### Current Stats
- **76 chunks** indexed (test documents)
- **3 source connectors** (base, local, gdrive)
- **5 core modules** working
- **3 user interfaces** (ingest CLI, query CLI, Streamlit)

---

## Next Steps: Phase 2 - Production Features

The system works end-to-end but needs production features for regular use.

### Priority 1: Incremental Ingestion (High Impact)

**Problem:** Currently re-ingests all documents every time, which is slow and wasteful.

**Solution:** Track which documents have been ingested and only process new/changed files.

**Implementation:**
1. Add document tracking table/file
   - Store: `{source_id: {hash, last_modified, chunks_created}}`
   - Could use SQLite or JSON file for MVP

2. Update `src/ingestion.py`:
   - Before ingesting, check if document exists
   - Compare modification date or content hash
   - Skip unchanged documents
   - Delete old chunks if document changed

3. Add `--force-reindex` flag to `ingest.py` to override

**Benefits:**
- Faster ingestion (only process new/changed files)
- Lower API costs (fewer embeddings)
- Can run frequently without waste

**Files to modify:**
- `src/ingestion.py` - Add change detection
- `ingest.py` - Add `--force-reindex` flag
- New: `src/document_tracker.py` (or use metadata in ChromaDB)

---

### Priority 2: Scheduled Ingestion (Automation)

**Problem:** User must manually run ingestion to get new documents.

**Solution:** Automatic periodic ingestion.

**Implementation Options:**

**Option A: Simple Cron Job** (Recommended for MVP)
```bash
# Add to crontab
0 */6 * * * cd ~/src/personal-rag && source .venv/bin/activate && python ingest.py --source-type gdrive --mode=accessed --max-results 100 >> /tmp/rag-cron.log 2>&1
```

**Option B: APScheduler** (More flexible)
- Create `scheduler.py`
- Run as background service
- Schedule hourly/daily ingestion
- Better error handling and logging

**Recommendation:** Start with cron (Option A), move to APScheduler if needed.

**Files to create:**
- `scheduler.py` (if using Option B)
- `scripts/setup-cron.sh` (helper script)

---

### Priority 3: Better Error Handling & Logging

**Current Issues:**
- Some PDFs fail silently (empty content, crypto errors)
- No notification when ingestion fails
- Logs are scattered

**Improvements:**

1. **Centralized logging:**
   - Create `logs/` directory
   - Log to file with rotation
   - Add structured logging (JSON format)

2. **Better error messages:**
   - Show which files failed and why
   - Suggest fixes (e.g., "install cryptography for encrypted PDFs")

3. **Notifications (optional):**
   - Email on ingestion errors
   - Slack webhook for failures

**Files to modify:**
- `src/ingestion.py` - Better error handling
- `src/connectors/gdrive.py` - More detailed error messages
- `src/config.py` - Add logging configuration
- New: `src/notifications.py` (optional)

---

### Priority 4: README & Documentation

**Create comprehensive README.md:**

```markdown
# Personal RAG System

Query your personal documents with AI.

## Quick Start
1. Setup: `uv venv && source .venv/bin/activate && uv pip install -e .`
2. Configure: `cp .env.example .env` and add OPENAI_API_KEY
3. Google Drive: Follow GOOGLE-OAUTH.md
4. Ingest: `python ingest.py --source-type gdrive --mode=accessed`
5. Chat: `streamlit run app.py`

## Features
- [List main features]

## Usage Examples
- [Common commands]

## Configuration
- [Environment variables]

## Troubleshooting
- [Common issues]
```

**Also document:**
- Architecture overview
- How to add new source connectors
- How to customize chunk size/embeddings
- Performance tips

---

## Phase 3: Production Deployment (Future)

After Phase 2 is solid, deploy to Hetzner server:

### 3.1 Containerization
- Create `Dockerfile` (multi-stage build)
- Create `docker-compose.yml`:
  - FastAPI service
  - Streamlit service
  - ChromaDB (or migrate to Qdrant)
  - PostgreSQL for metadata
  - Nginx reverse proxy

### 3.2 Server Setup
```bash
hcloud server create --name personal-rag --type cx21 --image ubuntu-22.04
```
- Install Docker
- Set up firewall
- Configure SSL with Let's Encrypt

### 3.3 Authentication
- Add OAuth2 login (Google)
- JWT tokens
- Protect endpoints
- User-specific collections

### 3.4 Monitoring
- Application logs
- Uptime monitoring
- Error tracking (Sentry)
- Usage metrics

**See HIGH-LEVEL-PLAN.md Phase 3 for details.**

---

## Known Issues & Technical Debt

### Performance
1. **GPT-5 is slow** (30-80 seconds per query)
   - This is expected with GPT-5
   - Consider adding streaming responses to show progress
   - Could add timeout warnings in UI

2. **No query caching**
   - Identical queries hit LLM every time
   - Could add Redis cache for common queries

3. **Large context windows**
   - Currently sending all 5 chunks to LLM
   - Could implement smarter context selection
   - Consider summarization for very long chunks

### Data Quality
1. **Some PDFs fail to parse**
   - Empty content for encrypted PDFs
   - Missing `cryptography` package
   - Could add fallback to OCR

2. **No deduplication**
   - Same document ingested multiple times creates duplicate chunks
   - Fixed by Priority 1 (incremental ingestion)

3. **Chunk size not optimal**
   - Current: 512 tokens with 50 overlap
   - May need tuning for different document types

---

## Quick Commands Reference

### Ingestion
```bash
# Google Drive (recently accessed)
python ingest.py --source-type gdrive --mode=accessed --max-results 100

# Google Drive (all files)
python ingest.py --source-type gdrive --mode=drive --max-results 50

# Local directory
python ingest.py --source ~/Documents/notes --source-type local

# Dry run (preview)
python ingest.py --source-type gdrive --mode=accessed --dry-run

# View stats
python ingest.py --stats

# Reset collection
python ingest.py --source-type local --source ~/notes --reset
```

### Querying
```bash
# CLI query
python query.py "your question" --top-k 5 --show-scores

# Filter by source
python query.py "question" --source-type gdrive

# API
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "your question", "top_k": 5}'

# Streamlit UI
streamlit run app.py
# Open http://localhost:8501
```

### Development
```bash
# Start API server
python api.py

# Start Streamlit
streamlit run app.py

# Run tests (when added)
pytest tests/

# Check collection stats
python query.py --stats
```

---

## Files & Structure Reference

```
personal-rag/
├── src/
│   ├── config.py          # Settings from .env
│   ├── models.py          # Pydantic models
│   ├── chunking.py        # Document splitting
│   ├── embeddings.py      # OpenAI embeddings
│   ├── ingestion.py       # Main ingestion pipeline
│   ├── retrieval.py       # ChromaDB queries
│   └── connectors/
│       ├── base.py        # Abstract connector
│       ├── local.py       # Local files
│       └── gdrive.py      # Google Drive
├── ingest.py              # CLI for ingestion
├── query.py               # CLI for queries
├── api.py                 # FastAPI backend
├── app.py                 # Streamlit UI
├── data/
│   └── chroma/            # ChromaDB storage (gitignored)
├── tests/
│   └── fixtures/          # Test documents
├── .env                   # Configuration (gitignored)
├── credentials.json       # Google OAuth (gitignored)
├── token.json            # Google token (gitignored)
├── pyproject.toml        # Dependencies
├── README.md             # Main documentation
├── DECISIONS.md          # Architecture decisions
├── HIGH-LEVEL-PLAN.md    # Full roadmap
├── CLAUDE.md             # Quick reference
├── GOOGLE-OAUTH.md       # OAuth setup guide
└── PLAN-REMAINDER.md     # This file
```

---

## Configuration Reference

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
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

### Google Drive Configuration
- `credentials.json` - OAuth client credentials (from Google Cloud Console)
- `token.json` - Access token (generated on first run)
- See GOOGLE-OAUTH.md for setup instructions

---

## Tips for Next Session

### If Starting Fresh
1. Check git status: `git status`
2. Review recent commits: `git log --oneline -10`
3. Check collection stats: `python query.py --stats`
4. Verify environment: `source .venv/bin/activate`

### If API/UI Not Working
1. Check if services running: `ps aux | grep -E "(uvicorn|streamlit)"`
2. View logs: `tail -f /tmp/api*.log /tmp/streamlit.log`
3. Restart services: `pkill -f "python api.py" && python api.py &`

### If Ingestion Issues
1. Test connection: `python ingest.py --source-type gdrive --list-folders`
2. Try dry-run: `python ingest.py --source-type gdrive --dry-run --max-results 5`
3. Check token: `ls -la token.json credentials.json`
4. Re-authenticate: `rm token.json && python ingest.py --source-type gdrive --list-folders`

### If Query Not Working
1. Check collection: `python query.py --stats`
2. Test simple query: `python query.py "test" --show-scores`
3. Try with lower threshold: `python query.py "test" --min-score 0.0`
4. Check ChromaDB: `ls -la data/chroma/`

---

## Success Criteria for Phase 2

Before moving to Phase 3, ensure:

- [ ] Incremental ingestion working (only processes new/changed files)
- [ ] Scheduled ingestion running (cron or APScheduler)
- [ ] Error handling improved (clear messages, logging)
- [ ] README.md complete with all setup instructions
- [ ] Can ingest 100+ documents without issues
- [ ] Can query documents with <5s response time
- [ ] UI is stable and user-friendly
- [ ] No data loss when restarting

---

## Questions to Consider

1. **Scale:** How many documents will you have?
   - Current: 76 chunks (test data)
   - Target: 100-2000 documents?
   - Affects: ChromaDB vs Qdrant decision

2. **Update Frequency:** How often do documents change?
   - Affects: Incremental ingestion strategy
   - Affects: Cron schedule (hourly, daily, weekly)

3. **Cost Budget:** How much to spend on OpenAI?
   - Embeddings: ~$0.01 per 1000 docs
   - Queries: ~$0.01 per query (GPT-5)
   - Affects: Caching strategy

4. **Multi-User:** Just you, or others too?
   - If multi-user: Need authentication (Phase 3)
   - If single-user: Can skip auth, simpler deployment

---

## Resources & References

- [LangChain Docs](https://python.langchain.com/)
- [ChromaDB Docs](https://docs.trychroma.com/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Streamlit Docs](https://docs.streamlit.io/)
- [OpenAI API Docs](https://platform.openai.com/docs)

## Project Links
- GitHub: https://github.com/joostremijn/personal-rag
- Last Commit: Check `git log -1`

---

**Next Session Start Here:**
1. Review this document
2. Check `git status` and `git log`
3. Start with Priority 1: Incremental Ingestion
4. Test thoroughly before moving to Priority 2

Good luck! 🚀
