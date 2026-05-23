from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from customer_agent.knowledge_ingestion import (  # noqa: E402
    PgKnowledgeChunkWriter,
    build_database_url_from_env,
    load_knowledge_chunks,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import RAG chunks into PostgreSQL knowledge_chunks.")
    parser.add_argument("--file", required=True, help="JSON file containing a chunk array or an object with a chunks array.")
    parser.add_argument("--database-url", default="", help="PostgreSQL URL. Defaults to DATABASE_URL or DB_* env vars.")
    parser.add_argument(
        "--deactivate-source",
        action="append",
        default=[],
        help="Soft-delete all active chunks for a source_doc_id before importing. Can be passed multiple times.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and print what would be imported.")
    args = parser.parse_args()

    chunks = load_knowledge_chunks(Path(args.file))
    database_url = args.database_url or build_database_url_from_env()
    if not database_url and not args.dry_run:
        raise SystemExit("DATABASE_URL or DB_HOST/DB_NAME/DB_USER/DB_PASS is required.")

    if args.dry_run:
        source_ids = sorted({chunk.source_doc_id for chunk in chunks})
        print(f"Validated {len(chunks)} chunks from {args.file}")
        print(f"Sources: {', '.join(source_ids)}")
        return

    writer = PgKnowledgeChunkWriter(database_url)
    result = writer.import_chunks_sync(chunks, args.deactivate_source)
    for source_doc_id, count in result.deactivated.items():
        print(f"Deactivated {count} chunks for source_doc_id={source_doc_id}")
    print(f"Imported {result.total} chunks.")
    print(f"Upserted ids: {', '.join(str(item) for item in result.upserted_ids)}")


if __name__ == "__main__":
    main()
