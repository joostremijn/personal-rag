#!/usr/bin/env python3
"""Streamlit chat interface for Personal RAG system."""

import logging
import time
from typing import List

import streamlit as st
from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.models import RetrievalResult, SourceType
from src.retrieval import RetrievalService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Personal RAG - Chat with Your Documents",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load settings
settings = get_settings()


@st.cache_resource
def get_retrieval_service():
    """Initialize and cache the retrieval service."""
    return RetrievalService()


@st.cache_resource
def get_llm():
    """Initialize and cache the LLM."""
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        openai_api_key=settings.openai_api_key,
    )


def format_sources(sources: List[RetrievalResult]) -> None:
    """Display retrieved sources in an expandable section.

    Args:
        sources: List of retrieval results to display
    """
    if not sources:
        return

    with st.expander(f"📚 View {len(sources)} Source(s)", expanded=False):
        for i, result in enumerate(sources, 1):
            st.markdown(f"### Source {i}: {result.metadata.title or 'Untitled'}")

            # Display metadata
            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"**Type:** {result.metadata.source_type.value}")
                if result.metadata.file_type:
                    st.caption(f"**Format:** {result.metadata.file_type}")
            with col2:
                if result.metadata.modified_at:
                    st.caption(f"**Modified:** {result.metadata.modified_at.strftime('%Y-%m-%d')}")
                st.caption(f"**Score:** {result.score:.3f}")
            with col3:
                st.caption(f"**Chunk:** {result.metadata.chunk_index + 1} of {result.metadata.total_chunks}")

            # URL if available
            if result.metadata.url:
                st.markdown(f"🔗 [Open in Drive]({result.metadata.url})")

            # Content preview
            st.markdown("**Content:**")
            content_preview = result.content
            if len(content_preview) > 500:
                content_preview = content_preview[:500] + "..."
            st.text(content_preview)

            if i < len(sources):
                st.divider()


def generate_answer(query: str, top_k: int, source_filter: List[str]) -> tuple:
    """Generate answer using RAG pipeline.

    Args:
        query: User query
        top_k: Number of sources to retrieve
        source_filter: List of source types to filter

    Returns:
        Tuple of (answer, sources, processing_time)
    """
    start_time = time.time()

    # Get services
    retrieval_service = get_retrieval_service()
    llm = get_llm()

    # Convert source filter
    source_type_filter = None
    if source_filter:
        source_type_filter = [SourceType(st_filter) for st_filter in source_filter]

    # Retrieve relevant chunks
    with st.spinner("🔍 Searching documents..."):
        results = retrieval_service.query(
            query_text=query,
            top_k=top_k,
            source_type_filter=source_type_filter,
        )

    if not results:
        return (
            "I couldn't find any relevant documents to answer your question. "
            "Try rephrasing your query or check if documents have been ingested.",
            [],
            time.time() - start_time,
        )

    # Build context
    context_parts = []
    for i, result in enumerate(results, 1):
        source_info = f"[Source {i}: {result.metadata.title or result.metadata.source}]"
        context_parts.append(f"{source_info}\n{result.content}\n")

    context = "\n---\n".join(context_parts)

    # Generate answer with LLM
    with st.spinner("💭 Generating answer..."):
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

        formatted_prompt = prompt_template.format(context=context, question=query)
        response = llm.invoke(formatted_prompt)
        answer = response.content

    processing_time = time.time() - start_time
    return answer, results, processing_time


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "sources" not in st.session_state:
    st.session_state.sources = {}

# Sidebar
with st.sidebar:
    st.title("⚙️ Settings")

    # Collection stats
    st.subheader("📊 Collection Stats")
    retrieval_service = get_retrieval_service()
    stats = retrieval_service.get_collection_stats()
    st.metric("Total Chunks", stats["total_chunks"])
    st.caption(f"Collection: {stats['collection_name']}")

    st.divider()

    # Query settings
    st.subheader("🔧 Query Settings")
    top_k = st.slider("Number of sources", min_value=1, max_value=10, value=5, help="How many document chunks to retrieve")

    source_filter = st.multiselect(
        "Filter by source type",
        options=["local", "gdrive"],
        default=[],
        help="Leave empty to search all sources",
    )

    st.divider()

    # Model info
    st.subheader("🤖 Model Info")
    st.caption(f"**LLM:** {settings.llm_model}")
    st.caption(f"**Embeddings:** {settings.embedding_model}")

    st.divider()

    # Clear chat button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.sources = {}
        st.rerun()

# Main chat interface
st.title("🔍 Personal RAG - Chat with Your Documents")
st.caption("Ask questions about your personal documents and get AI-powered answers")

# Display chat messages
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Display sources for assistant messages
        if message["role"] == "assistant" and idx in st.session_state.sources:
            format_sources(st.session_state.sources[idx])

# Chat input
if prompt := st.chat_input("Ask a question about your documents..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate and display assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()

        # Generate answer
        answer, sources, processing_time = generate_answer(prompt, top_k, source_filter)

        # Display answer
        message_placeholder.markdown(answer)

        # Store sources for this message
        message_idx = len(st.session_state.messages)
        st.session_state.sources[message_idx] = sources

        # Display sources
        format_sources(sources)

        # Display processing time
        st.caption(f"⏱️ Processing time: {processing_time:.2f}s")

    # Add assistant message to history
    st.session_state.messages.append({"role": "assistant", "content": answer})

# Footer
st.divider()
st.caption("💡 Tip: Be specific in your questions for better results")
