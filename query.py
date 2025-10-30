#!/usr/bin/env python3
"""CLI script for querying the Personal RAG system."""

import argparse
import logging
import sys
from typing import Optional

from src.config import get_settings
from src.retrieval import RetrievalService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for query CLI."""
    parser = argparse.ArgumentParser(
        description="Query documents in Personal RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple query
  python query.py "what are my notes about Python?"

  # Query with custom top_k
  python query.py "machine learning projects" --top-k 10

  # Query only Google Drive documents
  python query.py "meeting notes" --source-type gdrive

  # Show collection stats
  python query.py --stats
        """,
    )

    parser.add_argument(
        "query",
        type=str,
        nargs="?",
        help="Natural language query",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        help="Number of results to retrieve (default from config)",
    )

    parser.add_argument(
        "--source-type",
        type=str,
        choices=["local", "gdrive"],
        help="Filter by source type",
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Minimum similarity score (0-1, default: 0.0)",
    )

    parser.add_argument(
        "--collection",
        type=str,
        help="ChromaDB collection name (default from config)",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show collection statistics and exit",
    )

    parser.add_argument(
        "--show-scores",
        action="store_true",
        help="Show similarity scores in output",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Validate arguments
    if not args.stats and not args.query:
        parser.error("query argument is required when not using --stats")

    try:
        settings = get_settings()

        # Initialize retrieval service
        logger.info(f"Initializing retrieval service (collection: {args.collection or 'default'})")
        retrieval_service = RetrievalService(collection_name=args.collection)

        # Show stats if requested
        if args.stats:
            stats = retrieval_service.get_collection_stats()

            print("\n=== Collection Statistics ===")
            print(f"Collection: {stats['collection_name']}")
            print(f"Total chunks: {stats['total_chunks']}")
            print(f"Persist path: {stats['persist_path']}")
            print()

            return 0

        # Execute query
        logger.info(f"Executing query: '{args.query}'")

        # Build source type filter
        source_type_filter = None
        if args.source_type:
            from src.models import SourceType
            source_type_filter = [SourceType(args.source_type)]

        # Query
        results = retrieval_service.query(
            query_text=args.query,
            top_k=args.top_k,
            source_type_filter=source_type_filter,
            min_score=args.min_score,
        )

        if not results:
            print(f"\nNo results found for query: '{args.query}'")
            print("\nTry:")
            print("- Using different keywords")
            print("- Lowering --min-score threshold")
            print("- Checking if documents are ingested with: python query.py --stats")
            return 0

        # Display results
        print(f"\n=== Query Results ({len(results)} found) ===")
        print(f"Query: {args.query}\n")

        for i, result in enumerate(results, 1):
            print(f"--- Result {i} ---")

            if args.show_scores:
                print(f"Score: {result.score:.4f}")

            print(f"Source: {result.metadata.source}")
            print(f"Type: {result.metadata.source_type.value}")

            if result.metadata.title:
                print(f"Title: {result.metadata.title}")

            if result.metadata.url:
                print(f"URL: {result.metadata.url}")

            print(f"Chunk: {result.metadata.chunk_index + 1} of {result.metadata.total_chunks}")

            # Show content (truncate if too long)
            content = result.content
            if len(content) > 500:
                content = content[:500] + "..."
            print(f"\nContent:\n{content}\n")

        # Summary
        print(f"=== Found {len(results)} relevant chunks ===\n")

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"Error during query: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
