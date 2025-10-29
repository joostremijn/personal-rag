# Personal RAG System - Implementation Plan

This document outlines the phased implementation plan for building the Personal RAG system.

## Project Scope

Build a Retrieval-Augmented Generation (RAG) system that:
- Indexes personal content from multiple sources
- Enables natural language search and Q&A
- Scales from personal use to multi-user production
- Serves as a learning project for RAG architecture

## Timeline Overview

- **Phase 1 (MVP)**: 1-2 weeks - Local single-user system
- **Phase 2 (Multi-Source)**: 2-3 weeks - Add Google Drive, automated ingestion
- **Phase 3 (Production)**: 1-2 weeks - Deploy to Hetzner with auth
- **Phase 4 (Advanced)**: 2-3 weeks - Optimize retrieval and performance
- **Phase 5 (Multi-User)**: 2-3 weeks - Full multi-user support

---

## Phase 1: MVP - Local RAG System

**Goal**: Build working RAG system for local notes directory

**Duration**: 1-2 weeks

**Scope**:
- ✅ Project setup with uv
- ✅ Documentation (this file, DECISIONS.md, CLAUDE.md)
- Document chunking and embedding
- ChromaDB integration
- FastAPI backend
- Streamlit UI
- Manual ingestion script

### Tasks

#### 1.1 Project Setup
- [x] Create project structure
- [x] Write documentation files
- [ ] Set up uv with pyproject.toml
- [ ] Create .env.example template
- [ ] Create .gitignore
- [ ] Initialize git repository (optional)

**Files to create**:
- `pyproject.toml` - uv dependencies
- `.env.example` - Environment variable template
- `.gitignore` - Ignore .env, data/, .venv/, etc.
- `.python-version` - Python 3.11

#### 1.2 Core Ingestion Pipeline

**Create `src/config.py`**:
- Load environment variables with python-dotenv
- Define configuration constants (chunk size, model names, etc.)
- Validation for required env vars

**Create `src/chunking.py`**:
- Implement document loading from directory
- Recursive character text splitting
- Token counting with tiktoken
- Return list of Document objects with metadata

**Create `src/embeddings.py`**:
- OpenAI embedding interface
- Batch embedding for efficiency
- Error handling and retries

**Create `src/ingestion.py`**:
- Orchestrate: load docs → chunk → embed → store
- ChromaDB collection management
- Progress tracking
- Metadata tracking (source, timestamp, chunk position)

**Create `ingest.py`** (CLI script):
- Argument parsing (--source, --collection-name)
- Call ingestion pipeline
- Display progress and summary

**Test**: Ingest a small notes directory (5-10 files)

#### 1.3 Retrieval System

**Create `src/models.py`**:
- Pydantic models for Query, RetrievalResult, etc.
- Type safety throughout codebase

**Create `src/retrieval.py`**:
- ChromaDB query interface
- Vector similarity search
- Metadata filtering support
- Format results with scores and metadata

**Test**: Query ChromaDB and verify relevant chunks returned

#### 1.4 FastAPI Backend

**Create `api.py`**:
- FastAPI app setup
- CORS middleware (for local dev)
- Health check endpoint: `GET /health`
- Query endpoint: `POST /query`
  - Input: query text, optional filters
  - Output: Retrieved chunks + LLM response
- Ingest endpoint: `POST /ingest` (optional, for UI-triggered ingestion)

**LLM Integration**:
- LangChain RetrievalQA chain
- OpenAI GPT-5 integration
- Streaming response support
- System prompt for RAG behavior

**Test**:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what are my notes about Python?"}'
```

#### 1.5 Streamlit UI

**Create `app.py`**:
- Chat interface with message history
- Query input box
- Display chat messages (user + assistant)
- Show retrieved chunks (expandable section)
- Show source metadata (file names, snippets)
- Basic styling

**Features**:
- Session state for chat history
- Streaming response display
- Error handling and display
- Optional: File upload for ad-hoc ingestion

**Test**: Full end-to-end chat experience

#### 1.6 Testing & Documentation

**Create tests**:
- `tests/test_chunking.py` - Test chunking logic
- `tests/test_retrieval.py` - Test retrieval accuracy
- `tests/fixtures/` - Sample documents for testing

**Update README.md**:
- Quick start instructions
- Prerequisites
- Setup steps
- Usage examples

**Test**: Full workflow from ingestion to query

### Phase 1 Deliverables

- [ ] Working ingestion script for local directory
- [ ] ChromaDB populated with embedded chunks
- [ ] FastAPI backend with query endpoint
- [ ] Streamlit chat interface
- [ ] Basic tests passing
- [ ] Documentation complete

### Phase 1 Success Criteria

- Can ingest 100+ documents from notes directory
- Can ask questions and get relevant answers
- Response latency < 5 seconds
- Clear source attribution in responses
- Stable local development environment

---

## Phase 2: Multi-Source Ingestion

**Goal**: Add Google Drive integration and scheduled ingestion

**Duration**: 2-3 weeks

**Scope**:
- Google Drive OAuth integration
- Multiple document format parsers (PDF, DOCX, etc.)
- Scheduled ingestion jobs
- Change detection (incremental updates)
- Better metadata tracking

### Tasks

#### 2.1 Source Connector Abstraction

**Create `src/connectors/base.py`**:
- Abstract base class for source connectors
- Standard interface: `fetch_documents()`, `detect_changes()`

**Create `src/connectors/local.py`**:
- Refactor existing local directory ingestion
- Implement connector interface

#### 2.2 Google Drive Connector

**Create `src/connectors/gdrive.py`**:
- OAuth2 authentication flow
- Google Drive API integration
- Fetch files from Drive
- Download and parse various formats
- Track file metadata (modified date, owner, etc.)

**Setup**:
- Google Cloud Project
- Enable Drive API
- OAuth consent screen
- Store credentials securely

**Supported formats**:
- Google Docs (export as text)
- Google Sheets (export as CSV)
- PDFs, DOCX, TXT, etc.

#### 2.3 Document Parsers

**Create `src/parsers/`**:
- `pdf.py` - Parse PDFs (PyPDF2 or pdfplumber)
- `docx.py` - Parse DOCX (python-docx)
- `markdown.py` - Parse Markdown
- `text.py` - Plain text

**Update ingestion pipeline** to route by file type

#### 2.4 Scheduled Ingestion

**Option A: APScheduler** (simpler, in-process)
- Create `src/scheduler.py`
- Schedule hourly/daily ingestion jobs
- Run as background service

**Option B: Celery** (production-ready, distributed)
- Set up Redis for message broker
- Define Celery tasks for ingestion
- Create worker process
- Schedule periodic tasks

**Choose**: APScheduler for now, Celery path for Phase 3

#### 2.5 Incremental Updates

**Change detection**:
- Track document hashes or modification timestamps
- Compare with stored metadata
- Only process changed/new documents

**Update `src/ingestion.py`**:
- Check existing documents before re-processing
- Update or delete removed documents
- Efficient bulk operations

**Add PostgreSQL** (optional for Phase 2, required for Phase 3):
- Store document metadata
- Track ingestion history
- Enable efficient change detection

### Phase 2 Deliverables

- [ ] Google Drive connector working
- [ ] Multiple document formats supported
- [ ] Scheduled ingestion running
- [ ] Incremental updates working
- [ ] Extended test coverage

### Phase 2 Success Criteria

- Can ingest from Google Drive automatically
- Scheduled jobs run reliably
- Only new/changed documents re-processed
- Support 5+ document formats
- Metadata properly tracked

---

## Phase 3: Production Deployment

**Goal**: Deploy to Hetzner server with authentication

**Duration**: 1-2 weeks

**Scope**:
- Hetzner server setup
- Docker containerization
- PostgreSQL for metadata
- OAuth2 authentication
- HTTPS/TLS
- Secrets management

### Tasks

#### 3.1 Containerization

**Create `Dockerfile`**:
- Multi-stage build
- Python base image
- Install uv and dependencies
- Copy application code
- Set up entry points

**Create `docker-compose.yml`**:
- FastAPI backend service
- ChromaDB (or migrate to Qdrant)
- PostgreSQL service
- Redis (for Celery)
- Nginx (reverse proxy)
- Volume mounts for persistence

#### 3.2 Hetzner Server Setup

**Provision server**:
```bash
hcloud server create \
  --name personal-rag \
  --type cx21 \
  --image ubuntu-22.04 \
  --ssh-key your-key
```

**Server setup**:
- Install Docker & docker-compose
- Set up firewall (ufw)
- Configure SSH keys
- Set up automatic updates

#### 3.3 Database Migration

**Set up PostgreSQL**:
- User accounts table
- Document metadata table
- Ingestion history table
- OAuth tokens (encrypted)

**Create migrations**:
- Use Alembic for schema migrations
- Seed initial data

**Update application**:
- Replace in-memory metadata with PostgreSQL
- Add database connection pooling

#### 3.4 Authentication

**Implement OAuth2**:
- Google OAuth for login
- JWT token generation
- Token validation middleware

**Create `src/auth.py`**:
- OAuth flow handlers
- JWT encoding/decoding
- User session management

**Update API**:
- Add authentication middleware
- Protect endpoints with auth requirements
- Add user context to requests

**Create login UI**:
- OAuth login button
- Token storage (secure cookies)
- Logout functionality

#### 3.5 Deployment

**Configure secrets**:
- Environment variables for production
- Use HashiCorp Vault or AWS Secrets Manager (optional)
- Encrypted .env file on server

**Set up HTTPS**:
- Certbot for Let's Encrypt
- Nginx reverse proxy with SSL
- Auto-renewal of certificates

**Deploy**:
```bash
# On server
cd /opt/personal-rag
git pull
docker-compose down
docker-compose up -d --build
```

**Set up monitoring**:
- Application logs
- Error tracking (Sentry optional)
- Uptime monitoring

### Phase 3 Deliverables

- [ ] Docker containers running on Hetzner
- [ ] PostgreSQL for metadata
- [ ] OAuth2 authentication working
- [ ] HTTPS enabled
- [ ] Automated deployment process

### Phase 3 Success Criteria

- Application accessible via HTTPS
- Authentication required and working
- Data persisted across restarts
- Logs and monitoring in place
- Deployment documented

---

## Phase 4: Advanced Features

**Goal**: Optimize retrieval quality and performance

**Duration**: 2-3 weeks

**Scope**:
- Hybrid search (semantic + keyword)
- Re-ranking retrieved results
- Query optimization
- Caching
- Cost optimization
- Advanced metadata filtering

### Tasks

#### 4.1 Hybrid Search

**Add PostgreSQL full-text search**:
- Create FTS index on document content
- Implement keyword search endpoint

**Implement ensemble retrieval**:
- Combine vector and keyword search results
- Weighted scoring
- LangChain ensemble retriever

**Create `src/retrieval_hybrid.py`**:
- Parallel vector + keyword queries
- Result merging and deduplication
- Configurable weighting

#### 4.2 Re-ranking

**Add cross-encoder re-ranking**:
- Use model like `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Re-rank top-K retrieved chunks
- Improve relevance of final results

**Update retrieval pipeline**:
- Retrieve top-20 with vector search
- Re-rank to top-5 with cross-encoder
- Pass top-5 to LLM

#### 4.3 Query Optimization

**Implement query caching**:
- Redis cache for common queries
- Cache embeddings of frequent queries
- TTL-based invalidation

**Optimize embedding calls**:
- Batch similar queries if possible
- Cache query embeddings temporarily

#### 4.4 Advanced Metadata Filtering

**Add rich filters**:
- Date ranges (last week, last month)
- Source type (Drive, notes, email)
- Tags/labels
- Author/owner

**Update UI**:
- Filter sidebar
- Date picker
- Source checkboxes

#### 4.5 Cost Optimization

**Reduce embedding costs**:
- Only embed changed chunks
- Batch embedding calls

**Reduce LLM costs**:
- Optimize prompt length
- Use cheaper models for simple queries
- Implement query routing (simple vs. complex)

**Add usage tracking**:
- Track tokens used per user
- Display cost estimates
- Set usage limits (optional)

### Phase 4 Deliverables

- [ ] Hybrid search implemented
- [ ] Re-ranking improving results
- [ ] Query caching active
- [ ] Advanced filtering working
- [ ] Cost tracking in place

### Phase 4 Success Criteria

- Improved retrieval accuracy (measured by user feedback)
- Response latency < 3 seconds
- 30% reduction in LLM costs via optimization
- Rich filtering options available

---

## Phase 5: Multi-User Support

**Goal**: Support 100 users with data isolation

**Duration**: 2-3 weeks

**Scope**:
- User management system
- Per-user data isolation
- User quotas and limits
- Admin dashboard
- Billing integration (optional)

### Tasks

#### 5.1 User Management

**Enhance user system**:
- User registration flow
- Email verification
- Password reset (if not OAuth-only)
- Profile management

**Create admin interface**:
- User list and management
- Usage statistics per user
- Enable/disable users

#### 5.2 Data Isolation

**Implement user_id filtering**:
- Add `user_id` to all document metadata
- Filter all queries by authenticated user's `user_id`
- Test access control thoroughly

**Security audit**:
- Ensure no query can access other users' data
- Test edge cases (empty user_id, SQL injection, etc.)
- Code review for access control

#### 5.3 User Quotas

**Implement limits**:
- Document count per user (e.g., 2000 docs)
- Query rate limits (e.g., 100/day)
- Storage limits

**Track usage**:
- Documents ingested per user
- Queries per day
- Storage used

**Enforce limits**:
- Block ingestion when quota reached
- Rate limit API calls
- Display usage in UI

#### 5.4 Multi-Source Per User

**Allow users to connect sources**:
- OAuth connection per user for Google Drive
- Each user's own notes directory
- Future: Slack, email with user's OAuth

**Create source management UI**:
- Connect/disconnect sources
- View connected sources
- Trigger manual sync

#### 5.5 Admin Dashboard

**Create admin web UI**:
- User statistics
- System health metrics
- Error logs
- Usage analytics

**Monitoring**:
- Track ingestion jobs
- Query latency metrics
- Error rates

### Phase 5 Deliverables

- [ ] Multi-user system with data isolation
- [ ] User quotas enforced
- [ ] Per-user source connections
- [ ] Admin dashboard
- [ ] Security audit complete

### Phase 5 Success Criteria

- 100 users can use system concurrently
- Data isolation verified
- Quotas prevent abuse
- Admin can monitor system health
- No data leaks between users

---

## Future Enhancements (Post Phase 5)

### Additional Sources
- **Email** (Gmail, Outlook)
- **Slack** workspace messages
- **Calendar** events
- **GitHub** repositories
- **Notion** pages
- **Confluence** docs

### Advanced RAG Techniques
- **Multi-query retrieval** - Generate multiple queries from user input
- **Parent-child chunking** - Retrieve small chunks but provide larger context
- **Hypothetical questions** - Generate questions chunks might answer
- **Self-querying retrieval** - LLM generates filters from query

### Local LLM Support
- **Ollama integration** - Local LLM for privacy
- **Embedding models** - sentence-transformers for local embeddings
- **Cost comparison** - Local vs. API costs

### Enterprise Features
- **SSO integration** (SAML, LDAP)
- **Role-based access control**
- **Audit logging** with compliance reports
- **Data retention policies**
- **Backup and disaster recovery**

### Mobile App
- Native iOS/Android apps
- Offline mode with local storage
- Push notifications for new content

### Analytics
- Popular queries
- Content usage statistics
- Search effectiveness metrics
- User engagement tracking

---

## Risk Mitigation

### Technical Risks

**Risk**: ChromaDB doesn't scale to 200K documents
- **Mitigation**: Design abstraction for easy migration to Qdrant
- **Trigger**: Performance degrades at >50K docs

**Risk**: OpenAI API costs too high
- **Mitigation**: Implement caching, query optimization, usage limits
- **Trigger**: Monthly costs exceed $500

**Risk**: OAuth integration issues
- **Mitigation**: Use well-tested libraries (authlib), extensive testing
- **Trigger**: Security audit during Phase 3

**Risk**: Data leaks between users
- **Mitigation**: Thorough testing, security code review, access control tests
- **Trigger**: Before Phase 5 launch

### Operational Risks

**Risk**: Hetzner server downtime
- **Mitigation**: Backup strategy, monitoring, incident response plan
- **Trigger**: Uptime < 99%

**Risk**: Database corruption
- **Mitigation**: Regular backups, transaction safety, testing
- **Trigger**: Before production launch

**Risk**: API rate limits (OpenAI)
- **Mitigation**: Rate limiting, queuing, user education
- **Trigger**: If hit rate limits

---

## Success Metrics

### MVP (Phase 1)
- ✅ Can ingest and query local documents
- ✅ Response latency < 5 seconds
- ✅ Relevant answers 80%+ of the time

### Production (Phase 3)
- ✅ 99% uptime
- ✅ < 3 second response time
- ✅ Zero security incidents

### Multi-User (Phase 5)
- ✅ 100 active users
- ✅ 200K documents indexed
- ✅ 1000+ queries per day
- ✅ Cost per user < $5/month

---

## Next Steps

**Immediate** (This week):
1. ✅ Complete documentation (this file, DECISIONS.md, CLAUDE.md)
2. Set up project with uv
3. Implement core chunking logic
4. Test with small dataset

**Week 1-2** (Phase 1 MVP):
1. Complete ingestion pipeline
2. Build FastAPI backend
3. Create Streamlit UI
4. End-to-end testing

**Week 3-5** (Phase 2):
1. Google Drive integration
2. Scheduled ingestion
3. Document parsers

**Let's start building!**
