# Architecture Decision Records

This document tracks key architectural decisions for the Personal RAG system.

## DR-000: Dependency Management with uv

**Status**: Accepted
**Date**: 2025-10-29
**Context**: Need fast, reliable Python dependency management for local and production environments

**Decision**: Use `uv` for Python dependency management

**Rationale**:
- Extremely fast dependency resolution (10-100x faster than pip)
- Better dependency locking and reproducibility
- Modern, well-maintained tool
- Compatible with standard pyproject.toml
- Good for both local development and production deployments

**Consequences**:
- Team members need to install uv
- Some CI/CD pipelines may need updates for uv support
- Migration from Poetry/pip if needed

**Installation**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## DR-001: Vector Database Selection

**Status**: Accepted (MVP)
**Date**: 2025-10-29
**Context**: Need vector DB for ~100-1000 docs initially, scaling to 200K docs across 100 users

**Decision**: ChromaDB for MVP, Qdrant considered for production scaling

**Rationale**:
- ChromaDB excellent for learning and rapid prototyping
- Simple setup, great Python API
- Persistent storage out of the box
- Qdrant path available if we need production-grade multi-tenancy
- Both have good filtering capabilities

**Consequences**:
- Initial development faster with ChromaDB
- May need migration to Qdrant for production scale
- Should design retrieval interface to be swappable

**MVP Implementation**: ChromaDB with local persistence

---

## DR-002: Embedding Model Selection

**Status**: Accepted
**Date**: 2025-10-29
**Context**: Need fast embeddings for real-time queries, cost-effective at scale

**Decision**: OpenAI text-embedding-3-small

**Rationale**:
- Cost effective (~$0.02 per 1M tokens)
- Fast API response (~100-200ms for queries)
- Good quality for general documents
- 1536 dimensions, good balance of quality/size
- Widely supported and documented

**Consequences**:
- Dependency on OpenAI API availability
- API costs for embedding (minimal at MVP scale)
- Need to store embedding model version in metadata for potential re-indexing
- Can add local sentence-transformers later for offline dev

**Configuration**:
- Model: `text-embedding-3-small`
- Dimensions: 1536 (default)

---

## DR-003: Document Chunking Strategy

**Status**: Accepted
**Date**: 2025-10-29
**Context**: Need to split documents for embedding while preserving semantic meaning

**Decision**: Recursive character splitting with 512 token chunks and 50 token overlap

**Rationale**:
- 512 tokens fits well with embedding model context window
- Overlap prevents information loss at chunk boundaries
- Recursive splitting respects natural boundaries (paragraphs, sentences)
- LangChain's RecursiveCharacterTextSplitter implements this well
- Good balance between chunk size and retrieval precision

**Consequences**:
- Some long documents may generate many chunks
- Need metadata to track chunk relationships (source doc, position)
- Chunk boundaries may occasionally split concepts
- Can tune parameters based on testing

**Configuration**:
```python
chunk_size = 512  # tokens
chunk_overlap = 50  # tokens
separators = ["\n\n", "\n", ". ", " ", ""]
```

---

## DR-004: Retrieval Strategy (MVP)

**Status**: Accepted
**Date**: 2025-10-29
**Context**: MVP needs fast, quality retrieval; focus on semantic search first

**Decision**: Pure vector similarity search with basic metadata filtering

**Components**:
- Vector similarity via ChromaDB (cosine similarity)
- Metadata filtering (source, date, file type) via ChromaDB
- Top-k retrieval (k=5 initially)

**Rationale**:
- Modern embeddings are excellent for semantic search
- ChromaDB supports metadata filtering natively
- Simpler = faster to build and debug
- Good enough for 80% of use cases
- Can add hybrid search (BM25/keyword) post-MVP if needed

**Consequences**:
- No exact keyword matching initially
- Pure semantic search may miss exact phrase matches
- Easy to add hybrid retrieval later if needed

**Deferred to Post-MVP**:
- BM25/keyword search
- PostgreSQL full-text search
- Re-ranking with cross-encoders
- Ensemble retrieval

---

## DR-005: Multi-Tenancy and Authentication

**Status**: Deferred to Post-MVP
**Date**: 2025-10-29
**Context**: Support 100 users with isolated data access (production requirement)

**Decision**: For MVP - no authentication (local only). For production - metadata-based multi-tenancy with user_id filtering

**Rationale**:
- MVP is single-user, local development
- Production will need proper user isolation for security
- Metadata filtering approach is efficient in vector DBs

**Production Architecture** (future):
- OAuth2 (Google) for login
- JWT tokens for API authentication
- `user_id` embedded in all document metadata
- Query-time filtering by authenticated user's `user_id`
- PostgreSQL for user/token management

**Consequences**:
- MVP simpler without auth complexity
- Must implement rigorous access controls before production
- Security critical when implemented

---

## DR-006: Ingestion Pipeline Architecture

**Status**: Accepted (MVP - Simplified)
**Date**: 2025-10-29
**Context**: MVP needs simple ingestion from local notes directory

**Decision**: Simple CLI script for MVP, APScheduler/Celery for production

**MVP Implementation**:
- Python CLI script (`ingest.py`)
- Manual execution: `python ingest.py --source ~/notes`
- Synchronous processing
- Direct ChromaDB writes

**Production Path** (future):
- APScheduler for scheduled jobs (transitional)
- Celery + Redis for distributed workers (production scale)
- Source connectors for Drive, Email, Slack
- Change detection to avoid re-processing
- OAuth token management

**Rationale**:
- CLI script is simple and sufficient for MVP
- Easy to test and debug
- Production scaling path clear

**Consequences**:
- Manual ingestion for MVP
- Need to design for eventual automation
- Source connector abstraction helps future expansion

---

## DR-007: LLM Integration Strategy (MVP)

**Status**: Accepted
**Date**: 2025-10-29
**Context**: Need high-quality generation from retrieved context

**Decision**: OpenAI GPT-5 as primary LLM for MVP

**LLM**: OpenAI GPT-5 (gpt-5 model ID)

**Pipeline**:
1. User submits query
2. Embed query using text-embedding-3-small
3. Retrieve top-k chunks (k=5 initially)
4. Assemble context with metadata (source, date)
5. Prompt GPT-5 with system prompt + context + user query
6. Stream response to user

**Rationale**:
- GPT-5 is fast and high quality
- OpenAI API is well-documented and stable
- LangChain provides good abstractions
- Streaming improves perceived performance
- Can add Claude/other LLMs post-MVP easily

**Consequences**:
- Dependency on OpenAI API
- Need API key management
- Cost per query (manageable at MVP scale)
- Prompt engineering important for quality

**Post-MVP Additions**:
- Anthropic Claude support (long context useful for RAG)
- User-selectable LLM choice
- Cost tracking per query

---

## Summary: MVP Technology Stack

Based on decisions above:

**Core**:
- **Language**: Python 3.11+
- **Dependency Management**: uv
- **Vector DB**: ChromaDB
- **Embeddings**: OpenAI text-embedding-3-small
- **LLM**: OpenAI GPT-5
- **Framework**: LangChain

**API & UI**:
- **API**: FastAPI
- **UI**: Streamlit (development/MVP)

**Infrastructure** (MVP - Local):
- **Storage**: ChromaDB local persistence
- **Config**: python-dotenv for environment variables
- **No auth, no PostgreSQL, no job scheduler yet**

**Infrastructure** (Future - Production):
- **Database**: PostgreSQL (metadata, users)
- **Job Scheduler**: Celery + Redis
- **Auth**: OAuth2 + JWT
- **Deployment**: Docker + docker-compose on Hetzner
- **Vector DB**: Qdrant (if scaling needed)
