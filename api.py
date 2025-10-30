#!/usr/bin/env python3
"""FastAPI backend for Personal RAG system."""

import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config import get_settings
from src.models import QueryRequest, QueryResponse, RetrievalResult, SourceType
from src.retrieval import RetrievalService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global service instances
retrieval_service: Optional[RetrievalService] = None
llm: Optional[ChatOpenAI] = None
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app."""
    global retrieval_service, llm

    # Startup: Initialize services
    logger.info("Initializing Personal RAG API...")
    retrieval_service = RetrievalService()
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        openai_api_key=settings.openai_api_key,
        streaming=settings.llm_streaming,
    )
    logger.info(f"LLM initialized: {settings.llm_model}")
    logger.info("API ready!")

    yield

    # Shutdown: Cleanup
    logger.info("Shutting down API...")


# Create FastAPI app
app = FastAPI(
    title="Personal RAG API",
    description="API for querying personal documents with RAG",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    collection: str
    total_chunks: int


class SimpleQueryRequest(BaseModel):
    """Simple query request for API."""

    query: str
    top_k: Optional[int] = None
    source_type_filter: Optional[List[str]] = None
    include_sources: bool = True


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        stats = retrieval_service.get_collection_stats()
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            collection=stats["collection_name"],
            total_chunks=stats["total_chunks"],
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.post("/query", response_model=QueryResponse)
async def query_documents(request: SimpleQueryRequest):
    """Query documents and generate answer with LLM.

    Args:
        request: Query request with query text and optional filters

    Returns:
        QueryResponse with answer and source chunks
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    start_time = time.time()

    try:
        # Step 1: Retrieve relevant chunks
        logger.info(f"Processing query: '{request.query}'")

        # Convert source_type filter
        source_type_filter = None
        if request.source_type_filter:
            source_type_filter = [SourceType(st) for st in request.source_type_filter]

        results = retrieval_service.query(
            query_text=request.query,
            top_k=request.top_k,
            source_type_filter=source_type_filter,
        )

        if not results:
            # No results found
            processing_time = time.time() - start_time
            return QueryResponse(
                query=request.query,
                answer="I couldn't find any relevant documents to answer your question. "
                "Try rephrasing your query or check if documents have been ingested.",
                sources=[],
                processing_time=processing_time,
            )

        # Step 2: Prepare context from retrieved chunks
        context_parts = []
        for i, result in enumerate(results, 1):
            source_info = f"[Source {i}: {result.metadata.title or result.metadata.source}]"
            context_parts.append(f"{source_info}\n{result.content}\n")

        context = "\n---\n".join(context_parts)

        # Step 3: Generate answer with LLM
        prompt_template = """You are a helpful assistant that answers questions based on the provided context from the user's personal documents.

Context from relevant documents:
{context}

User Question: {question}

Instructions:
- Answer the question based on the context provided above
- If the context doesn't contain enough information, say so clearly
- Cite sources by referring to [Source 1], [Source 2], etc.
- Be concise and direct
- If the question is unclear, ask for clarification

Answer:"""

        # Format prompt
        formatted_prompt = prompt_template.format(context=context, question=request.query)

        # Generate answer
        logger.info("Generating answer with LLM...")
        response = llm.invoke(formatted_prompt)
        answer = response.content

        processing_time = time.time() - start_time

        logger.info(f"Query processed in {processing_time:.2f}s")

        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=results if request.include_sources else [],
            processing_time=processing_time,
        )

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/stats")
async def get_stats():
    """Get collection statistics."""
    try:
        stats = retrieval_service.get_collection_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


# Main entry point for running with uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
