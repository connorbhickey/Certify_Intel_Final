"""
Setup script for vector store tables in PostgreSQL.
Run: python setup_vector_store.py

This creates:
- pgvector extension
- knowledge_documents table
- document_chunks table with vector embeddings
- HNSW index for fast vector search
"""
import asyncio
import os
import sys

# Load environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


async def setup_vector_store():
    """Create vector store tables in PostgreSQL."""
    import asyncpg

    # Get PostgreSQL connection string
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/certify_intel")

    # Convert SQLAlchemy URL format if needed
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    print("=" * 60)
    print("VECTOR STORE SETUP")
    print("=" * 60)
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    print()

    try:
        conn = await asyncpg.connect(db_url)
        print("[OK] Connected to PostgreSQL")

        # Create pgvector extension
        print("\n1. Creating pgvector extension...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("   [OK] pgvector extension enabled")

        # Check pgvector version
        version = await conn.fetchval("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        print(f"   pgvector version: {version}")

        # Create knowledge_documents table
        print("\n2. Creating knowledge_documents table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                id VARCHAR(36) PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_type VARCHAR(20) NOT NULL,
                content_hash VARCHAR(64) UNIQUE NOT NULL,
                uploaded_by VARCHAR(255),
                file_size_bytes INTEGER DEFAULT 0,
                chunk_count INTEGER DEFAULT 0,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        print("   [OK] knowledge_documents table created")

        # Create document_chunks table
        print("\n3. Creating document_chunks table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id SERIAL PRIMARY KEY,
                document_id VARCHAR(36) NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                token_count INTEGER DEFAULT 0,
                embedding vector(1536),
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(document_id, chunk_index)
            )
        """)
        print("   [OK] document_chunks table created")

        # Create indexes
        print("\n4. Creating indexes...")

        # Check if HNSW index exists
        index_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_document_chunks_embedding'
            )
        """)

        if not index_exists:
            print("   Creating HNSW index for vector search (this may take a moment)...")
            await conn.execute("""
                CREATE INDEX idx_document_chunks_embedding
                ON document_chunks
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 128)
            """)
            print("   [OK] HNSW index created")
        else:
            print("   [OK] HNSW index already exists")

        # Create other indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON knowledge_documents(content_hash)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_file_type ON knowledge_documents(file_type)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id)")
        print("   [OK] Additional indexes created")

        # Verify tables
        print("\n5. Verifying setup...")
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('knowledge_documents', 'document_chunks')
        """)

        for table in tables:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table['table_name']}")
            print(f"   - {table['table_name']}: {count} rows")

        await conn.close()

        print()
        print("=" * 60)
        print("VECTOR STORE SETUP COMPLETE")
        print("=" * 60)
        print()
        print("You can now:")
        print("  1. Ingest documents: python test_rag_pipeline.py")
        print("  2. Search knowledge base: python vector_store.py search 'your query'")

    except Exception as e:
        import logging
        logging.exception(f"[FAIL] Setup error: {e}")


if __name__ == "__main__":
    asyncio.run(setup_vector_store())
