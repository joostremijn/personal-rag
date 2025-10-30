#!/usr/bin/env python3
"""CLI script for ingesting documents into Personal RAG system."""

import argparse
import logging
import sys
from pathlib import Path

from src.config import get_settings
from src.connectors.gdrive import GoogleDriveConnector
from src.connectors.local import LocalFileConnector
from src.ingestion import IngestionPipeline
from src.models import SourceType

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for ingestion CLI."""
    parser = argparse.ArgumentParser(
        description="Ingest documents into Personal RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest from local directory
  python ingest.py --source ~/Documents/notes --source-type local

  # Ingest from Google Drive (all accessible files, default mode)
  python ingest.py --source-type gdrive --max-results 100

  # Ingest recently accessed files (last 2 years, sorted by recency)
  python ingest.py --source-type gdrive --mode=accessed --max-results 500

  # Ingest recently accessed files (last 6 months)
  python ingest.py --source-type gdrive --mode=accessed --days-back 180

  # Ingest from specific folder (recently accessed only)
  python ingest.py --source-type gdrive --mode=accessed --folder-id "abc123xyz"

  # Dry run - see what would be ingested without actually ingesting
  python ingest.py --source-type gdrive --mode=accessed --max-results 10 --dry-run

  # Reset collection before ingesting
  python ingest.py --source ~/Documents/notes --source-type local --reset

  # List Google Drive folders
  python ingest.py --source-type gdrive --list-folders

  # View collection statistics
  python ingest.py --stats
        """,
    )

    parser.add_argument(
        "--source",
        type=str,
        help="Source path for local files (directory or file)",
    )

    parser.add_argument(
        "--source-type",
        type=str,
        choices=["local", "gdrive"],
        help="Type of source to ingest from",
    )

    parser.add_argument(
        "--folder-id",
        type=str,
        help="Google Drive folder ID (only for gdrive source type)",
    )

    parser.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Maximum number of files to fetch from Google Drive (default: 100)",
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["drive", "accessed"],
        default="drive",
        help="Google Drive ingestion mode: 'drive' for all files (default), "
        "'accessed' for recently accessed files sorted by recency",
    )

    parser.add_argument(
        "--days-back",
        type=int,
        default=730,
        help="Number of days to look back for accessed files (default: 730 = ~2 years). "
        "Only used with --mode=accessed",
    )

    parser.add_argument(
        "--collection",
        type=str,
        help="ChromaDB collection name (default from config)",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset collection (delete all existing documents) before ingesting",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show collection statistics and exit",
    )

    parser.add_argument(
        "--list-folders",
        action="store_true",
        help="List Google Drive folders and exit (requires --source-type gdrive)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be ingested without actually ingesting them",
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Recursively scan subdirectories (default: True)",
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
    if not args.stats and not args.list_folders:
        if not args.source_type:
            parser.error("--source-type is required when not using --stats or --list-folders")

        if args.source_type == "local" and not args.source:
            parser.error("--source is required for local source type")

    try:
        settings = get_settings()

        # Show stats if requested
        if args.stats:
            pipeline = IngestionPipeline(collection_name=args.collection)
            stats = pipeline.get_collection_stats()

            print("\n=== Collection Statistics ===")
            print(f"Collection: {stats['collection_name']}")
            print(f"Total chunks: {stats['total_chunks']}")
            print(f"Persist path: {stats['persist_path']}")
            print("\nSource types:")
            for source_type, count in stats["source_types"].items():
                print(f"  {source_type}: {count}")
            print()

            return 0

        # List Google Drive folders if requested
        if args.list_folders:
            if args.source_type != "gdrive":
                parser.error("--list-folders requires --source-type gdrive")

            print("\n=== Listing Google Drive Folders ===")
            connector = GoogleDriveConnector()
            folders = connector.list_folders(parent_folder_id=args.folder_id)

            if not folders:
                print("No folders found")
            else:
                print(f"\nFound {len(folders)} folders:\n")
                for folder in folders:
                    print(f"  {folder['name']}")
                    print(f"    ID: {folder['id']}")
                    print(f"    Modified: {folder['modifiedTime']}")
                    print()

            return 0

        # Initialize pipeline
        logger.info(f"Initializing ingestion pipeline (collection: {args.collection or 'default'})")
        pipeline = IngestionPipeline(
            collection_name=args.collection,
            reset_collection=args.reset,
        )

        # Fetch documents based on source type
        if args.source_type == "local":
            logger.info(f"Fetching documents from local source: {args.source}")
            connector = LocalFileConnector()
            documents = connector.fetch_documents(
                source_path=args.source,
                recursive=args.recursive,
            )

        elif args.source_type == "gdrive":
            logger.info("Fetching documents from Google Drive")
            connector = GoogleDriveConnector()

            if not connector.validate_connection():
                logger.error("Failed to connect to Google Drive")
                return 1

            documents = connector.fetch_documents(
                folder_id=args.folder_id,
                max_results=args.max_results,
                mode=args.mode,
                days_back=args.days_back,
            )

        else:
            logger.error(f"Unsupported source type: {args.source_type}")
            return 1

        if not documents:
            logger.warning("No documents found to ingest")
            return 0

        # Dry run - just list files without ingesting
        if args.dry_run:
            print(f"\n=== Dry Run - Would Ingest {len(documents)} Documents ===\n")
            for i, doc in enumerate(documents, 1):
                print(f"{i}. {doc.metadata.title}")
                print(f"   Source: {doc.metadata.source}")
                print(f"   Type: {doc.metadata.file_type or 'N/A'}")
                print(f"   Modified: {doc.metadata.modified_at.strftime('%Y-%m-%d %H:%M:%S') if doc.metadata.modified_at else 'N/A'}")
                if doc.metadata.url:
                    print(f"   URL: {doc.metadata.url}")
                if doc.metadata.additional.get("viewed_by_me_time"):
                    print(f"   Last Viewed: {doc.metadata.additional['viewed_by_me_time']}")
                print(f"   Size: {len(doc.content)} characters")
                print()

            print(f"Total: {len(documents)} documents")
            print("\nRun without --dry-run to actually ingest these files.")
            return 0

        # Ingest documents
        logger.info(f"Starting ingestion of {len(documents)} documents")
        stats = pipeline.ingest_documents(documents)

        # Print summary
        print("\n=== Ingestion Summary ===")
        print(f"Total documents: {stats.total_documents}")
        print(f"Total chunks: {stats.total_chunks}")
        print(f"Failed documents: {stats.failed_documents}")
        print(f"Processing time: {stats.processing_time:.2f}s")

        if stats.failed_files:
            print(f"\nFailed files:")
            for failed_file in stats.failed_files:
                print(f"  - {failed_file}")

        print()

        # Show updated collection stats
        collection_stats = pipeline.get_collection_stats()
        print(f"Collection now contains {collection_stats['total_chunks']} total chunks")

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"Error during ingestion: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
