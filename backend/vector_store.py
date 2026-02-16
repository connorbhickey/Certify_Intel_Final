"""
Certify Intel v7.0 - Vector Store Module
=========================================

Production-grade vector search using PostgreSQL + pgvector.

Features:
- Semantic search with cosine similarity
- Batch embedding with OpenAI text-embedding-3-small
- Metadata filtering for scoped queries
- Connection pooling for high throughput

Performance Targets:
- <500ms for 10K vectors at 99% recall
- <100ms for cached embeddings

Usage:
    from vector_store import VectorStore

    store = VectorStore()

    # Insert documents
    await store.batch_insert(doc_id, chunks)

    # Search
    results = await store.search("pricing strategy", limit=10)
"""

import os
import asyncio
import hashlib
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import numpy as np

# Lazy imports for optional dependencies
_asyncpg = None
_openai_client = None

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from vector similarity search."""
    chunk_id: int
    document_id: str
    content: str
    metadata: Dict[str, Any]
    similarity: float


@dataclass
class DocumentChunk:
    """A chunk of text with embedding."""
    chunk_index: int
    content: str
    embedding: np.ndarray
    metadata: Optional[Dict[str, Any]] = None
    token_count: Optional[int] = None


class VectorStore:
    """
    PostgreSQL + pgvector vector store for semantic search.

    Index Types:
    - HNSW (default): Fast approximate nearest neighbor, good up to ~10M vectors
    - StreamingDiskANN: For 10M-100M+ vectors, requires pgvectorscale extension

    To upgrade to StreamingDiskANN for 50M+ scale:
        store = VectorStore()
        await store.create_streamingdiskann_index()
    """

    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    DEFAULT_BATCH_SIZE = 100

    # Index configuration
    INDEX_TYPE_HNSW = "hnsw"
    INDEX_TYPE_DISKANN = "diskann"

    def __init__(
        self,
        connection_string: Optional[str] = None,
        pool_size: int = 10
    ):
        """
        Initialize vector store.

        Args:
            connection_string: PostgreSQL connection string
                             Format: postgresql://user:pass@host:port/db
            pool_size: Connection pool size for concurrent operations
        """
        self.connection_string = connection_string or os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/certify_intel"
        )
        self.pool_size = pool_size
        self._pool = None
        self._embedding_cache: Dict[str, np.ndarray] = {}

    async def _get_pool(self):
        """Get or create async connection pool."""
        global _asyncpg

        if self._pool is None:
            try:
                import asyncpg
                _asyncpg = asyncpg

                # Convert SQLAlchemy URL to asyncpg format if needed
                conn_str = self.connection_string
                if conn_str.startswith("postgresql+asyncpg://"):
                    conn_str = conn_str.replace("postgresql+asyncpg://", "postgresql://")

                self._pool = await asyncpg.create_pool(
                    conn_str,
                    min_size=2,
                    max_size=self.pool_size,
                    command_timeout=30
                )
                logger.info(f"Created asyncpg connection pool (size={self.pool_size})")
            except ImportError:
                raise ImportError(
                    "asyncpg is required for vector store. "
                    "Install with: pip install asyncpg"
                )

        return self._pool

    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for text using OpenAI.

        Args:
            text: Text to embed

        Returns:
            numpy array of embedding vector (1536 dimensions)
        """
        # Check cache first
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        global _openai_client

        if _openai_client is None:
            try:
                from openai import AsyncOpenAI
                _openai_client = AsyncOpenAI()
            except ImportError:
                raise ImportError(
                    "openai is required for embeddings. "
                    "Install with: pip install openai"
                )

        response = await _openai_client.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=text
        )

        embedding = np.array(response.data[0].embedding)

        # Cache for reuse
        self._embedding_cache[cache_key] = embedding

        # Limit cache size
        if len(self._embedding_cache) > 1000:
            # Remove oldest half
            keys = list(self._embedding_cache.keys())[:500]
            for k in keys:
                del self._embedding_cache[k]

        return embedding

    async def batch_embed(self, texts: List[str]) -> List[np.ndarray]:
        """
        Batch embed multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        global _openai_client

        if _openai_client is None:
            try:
                from openai import AsyncOpenAI
                _openai_client = AsyncOpenAI()
            except ImportError:
                raise ImportError("openai is required for embeddings")

        # Process in batches of 2048 (OpenAI limit)
        all_embeddings = []

        for i in range(0, len(texts), 2048):
            batch = texts[i:i+2048]

            response = await _openai_client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=batch
            )

            embeddings = [np.array(e.embedding) for e in response.data]
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.7,
        filter_metadata: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 15.0
    ) -> List[SearchResult]:
        """
        Semantic search for similar document chunks.

        Args:
            query: Natural language query
            limit: Maximum results to return
            min_similarity: Minimum cosine similarity (0-1)
            filter_metadata: JSONB filter for metadata
            timeout_seconds: Timeout for embedding + search (default: 15.0)

        Returns:
            List of SearchResult objects ordered by similarity
        """
        try:
            # Get query embedding with timeout
            query_embedding = await asyncio.wait_for(
                self.embed_text(query),
                timeout=timeout_seconds / 2  # Half for embedding
            )

            # Search with embedding with remaining timeout
            return await asyncio.wait_for(
                self.search_by_embedding(
                    query_embedding,
                    limit=limit,
                    min_similarity=min_similarity,
                    filter_metadata=filter_metadata
                ),
                timeout=timeout_seconds / 2  # Half for search
            )
        except asyncio.TimeoutError:
            logger.warning(f"Vector search timed out after {timeout_seconds}s for query: {query[:50]}...")
            return []
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def search_by_embedding(
        self,
        embedding: np.ndarray,
        limit: int = 10,
        min_similarity: float = 0.7,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search by pre-computed embedding vector.

        Args:
            embedding: Query embedding vector
            limit: Maximum results to return
            min_similarity: Minimum cosine similarity (0-1)
            filter_metadata: JSONB filter for metadata

        Returns:
            List of SearchResult objects ordered by similarity
        """
        pool = await self._get_pool()

        # Convert numpy array to pgvector string format '[x,y,z,...]'
        if hasattr(embedding, 'tolist'):
            embedding = embedding.tolist()
        embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

        async with pool.acquire() as conn:
            # Build query with optional metadata filter
            if filter_metadata:
                import json
                query = """
                    SELECT
                        id as chunk_id,
                        document_id,
                        content,
                        metadata,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM document_chunks
                    WHERE metadata @> $2::jsonb
                    AND 1 - (embedding <=> $1::vector) >= $3
                    ORDER BY embedding <=> $1::vector
                    LIMIT $4
                """
                rows = await conn.fetch(
                    query,
                    embedding_str,
                    json.dumps(filter_metadata),
                    min_similarity,
                    limit
                )
            else:
                query = """
                    SELECT
                        id as chunk_id,
                        document_id,
                        content,
                        metadata,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM document_chunks
                    WHERE 1 - (embedding <=> $1::vector) >= $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """
                rows = await conn.fetch(
                    query,
                    embedding_str,
                    min_similarity,
                    limit
                )

        import json as json_module

        def parse_metadata(meta):
            """Parse metadata from various formats."""
            if not meta:
                return {}
            if isinstance(meta, dict):
                return meta
            if isinstance(meta, str):
                try:
                    return json_module.loads(meta)
                except Exception:
                    return {}
            return dict(meta)

        return [
            SearchResult(
                chunk_id=row['chunk_id'],
                document_id=row['document_id'],
                content=row['content'],
                metadata=parse_metadata(row['metadata']),
                similarity=float(row['similarity'])
            )
            for row in rows
        ]

    async def insert_document(
        self,
        document_id: str,
        filename: str,
        file_type: str,
        content_hash: str,
        uploaded_by: str,
        file_size_bytes: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Insert a knowledge document record, or return existing document ID if duplicate.

        Args:
            document_id: Unique document ID (UUID) for new document
            filename: Original filename
            file_type: File type (pdf, docx, txt, md)
            content_hash: SHA256 hash of content
            uploaded_by: User who uploaded
            file_size_bytes: File size in bytes
            metadata: Additional metadata

        Returns:
            document_id if inserted, or existing document ID if duplicate content_hash
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            import json

            # First check if document with this content_hash already exists
            existing = await conn.fetchrow(
                "SELECT id FROM knowledge_documents WHERE content_hash = $1",
                content_hash
            )

            if existing:
                # Return existing document ID for updates
                return existing['id']

            # Insert new document
            await conn.execute(
                """
                INSERT INTO knowledge_documents
                    (id, filename, file_type, content_hash, uploaded_by, file_size_bytes, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                document_id,
                filename,
                file_type,
                content_hash,
                uploaded_by,
                file_size_bytes,
                json.dumps(metadata or {})
            )
            return document_id

    async def batch_insert_chunks(
        self,
        document_id: str,
        chunks: List[DocumentChunk]
    ) -> int:
        """
        Batch insert document chunks with embeddings.

        Args:
            document_id: Parent document ID
            chunks: List of DocumentChunk objects

        Returns:
            Number of chunks inserted
        """
        if not chunks:
            return 0

        pool = await self._get_pool()

        async with pool.acquire() as conn:
            import json

            # Helper to convert numpy array to pgvector string format
            def embedding_to_pgvector(emb) -> str:
                """Convert embedding array to pgvector string format '[x,y,z,...]'"""
                if hasattr(emb, 'tolist'):
                    emb = emb.tolist()
                return '[' + ','.join(str(x) for x in emb) + ']'

            # Prepare data for batch insert
            records = [
                (
                    document_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.token_count or 0,
                    embedding_to_pgvector(chunk.embedding),  # Convert to pgvector format
                    json.dumps(chunk.metadata or {})
                )
                for chunk in chunks
            ]

            # Batch insert
            await conn.executemany(
                """
                INSERT INTO document_chunks
                    (document_id, chunk_index, content, token_count, embedding, metadata)
                VALUES ($1, $2, $3, $4, $5::vector, $6::jsonb)
                ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                    content = EXCLUDED.content,
                    token_count = EXCLUDED.token_count,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata
                """,
                records
            )

            # Update chunk count in parent document
            await conn.execute(
                """
                UPDATE knowledge_documents
                SET chunk_count = $1, updated_at = NOW()
                WHERE id = $2
                """,
                len(chunks),
                document_id
            )

        return len(chunks)

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and all its chunks.

        Args:
            document_id: Document ID to delete

        Returns:
            True if deleted, False if not found
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # Chunks are deleted via CASCADE
            result = await conn.execute(
                "DELETE FROM knowledge_documents WHERE id = $1",
                document_id
            )
            return "DELETE 1" in result

    async def get_document_chunks(
        self,
        document_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all chunks for a document (without embeddings).

        Args:
            document_id: Document ID

        Returns:
            List of chunk dictionaries
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT chunk_index, content, token_count, metadata
                FROM document_chunks
                WHERE document_id = $1
                ORDER BY chunk_index
                """,
                document_id
            )

        return [
            {
                "chunk_index": row['chunk_index'],
                "content": row['content'],
                "token_count": row['token_count'],
                "metadata": dict(row['metadata']) if row['metadata'] else {}
            }
            for row in rows
        ]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get vector store statistics.

        Returns:
            Dict with document count, chunk count, avg embedding time
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            doc_count = await conn.fetchval(
                "SELECT COUNT(*) FROM knowledge_documents"
            )
            chunk_count = await conn.fetchval(
                "SELECT COUNT(*) FROM document_chunks"
            )
            avg_tokens = await conn.fetchval(
                "SELECT AVG(token_count) FROM document_chunks"
            )

        return {
            "document_count": doc_count or 0,
            "chunk_count": chunk_count or 0,
            "avg_tokens_per_chunk": round(avg_tokens or 0, 1),
            "embedding_model": self.EMBEDDING_MODEL,
            "embedding_dimensions": self.EMBEDDING_DIMENSIONS,
            "cache_size": len(self._embedding_cache)
        }

    # =========================================================================
    # PGVECTORSCALE SUPPORT (For 50M+ vector scale)
    # =========================================================================

    async def check_pgvectorscale_extension(self) -> bool:
        """
        Check if pgvectorscale extension is installed.

        pgvectorscale provides StreamingDiskANN for 10x better performance
        at 50M+ vector scale compared to HNSW.

        Returns:
            True if pgvectorscale is available
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM pg_available_extensions
                    WHERE name = 'vectorscale'
                )
                """
            )
            return bool(result)

    async def install_pgvectorscale_extension(self) -> bool:
        """
        Install pgvectorscale extension if available.

        Requires superuser or extension installation privileges.
        For Timescale Cloud, this is pre-installed.

        Returns:
            True if installed successfully
        """
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE")
                logger.info("pgvectorscale extension installed successfully")
                return True
        except Exception as e:
            logger.warning(f"Could not install pgvectorscale: {e}")
            return False

    async def create_streamingdiskann_index(
        self,
        num_neighbors: int = 50,
        search_list_size: int = 100,
        max_alpha: float = 1.2,
        num_dimensions: int = None,
        num_bits_per_dimension: int = 2
    ) -> bool:
        """
        Create StreamingDiskANN index for 50M+ vector scale.

        StreamingDiskANN provides:
        - 10x better price-performance vs HNSW at scale
        - Sub-linear memory usage (doesn't load entire index in RAM)
        - Continuous index updates without rebuild
        - 99.5%+ recall at 10ms latency for 100M+ vectors

        Args:
            num_neighbors: Number of neighbors per node (default: 50)
                          Higher = better recall, more memory
            search_list_size: Search beam width (default: 100)
                             Higher = better recall, slower search
            max_alpha: Pruning parameter (default: 1.2)
                      Lower = more aggressive pruning, less memory
            num_dimensions: Override embedding dimensions (default: auto)
            num_bits_per_dimension: Quantization bits (default: 2)
                                   Lower = less memory, slightly lower recall

        Returns:
            True if index created successfully
        """
        pool = await self._get_pool()

        # Use configured dimensions or auto-detect
        dimensions = num_dimensions or self.EMBEDDING_DIMENSIONS

        try:
            async with pool.acquire() as conn:
                # First, check if pgvectorscale is available
                has_extension = await self.check_pgvectorscale_extension()
                if not has_extension:
                    # Try to install it
                    installed = await self.install_pgvectorscale_extension()
                    if not installed:
                        logger.error(
                            "pgvectorscale extension not available. "
                            "Install with: CREATE EXTENSION vectorscale; "
                            "Or use Timescale Cloud for managed setup."
                        )
                        return False

                # Drop existing HNSW index if present
                await conn.execute(
                    """
                    DROP INDEX IF EXISTS document_chunks_embedding_idx
                    """
                )

                # Create StreamingDiskANN index
                # Note: This can take significant time for large datasets
                index_sql = f"""
                    CREATE INDEX document_chunks_embedding_diskann_idx
                    ON document_chunks
                    USING diskann (embedding)
                    WITH (
                        num_neighbors = {num_neighbors},
                        search_list_size = {search_list_size},
                        max_alpha = {max_alpha},
                        num_dimensions = {dimensions},
                        num_bits_per_dimension = {num_bits_per_dimension}
                    )
                """
                await conn.execute(index_sql)

                logger.info(
                    f"StreamingDiskANN index created: "
                    f"neighbors={num_neighbors}, search_list={search_list_size}, "
                    f"bits_per_dim={num_bits_per_dimension}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to create StreamingDiskANN index: {e}")
            return False

    async def get_index_info(self) -> Dict[str, Any]:
        """
        Get information about current vector index.

        Returns:
            Dict with index type, size, and configuration
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # Check what indexes exist on embedding column
            indexes = await conn.fetch(
                """
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = 'document_chunks'
                AND indexdef LIKE '%embedding%'
                """
            )

            if not indexes:
                return {
                    "index_type": None,
                    "index_name": None,
                    "recommendation": (
                        "No vector index found. Create with "
                        "create_hnsw_index() or create_streamingdiskann_index()"
                    )
                }

            # Parse index type from definition
            index_info = {
                "indexes": [],
                "primary_type": None
            }

            for idx in indexes:
                idx_name = idx['indexname']
                idx_def = idx['indexdef']

                if 'diskann' in idx_def.lower():
                    idx_type = self.INDEX_TYPE_DISKANN
                elif 'hnsw' in idx_def.lower():
                    idx_type = self.INDEX_TYPE_HNSW
                else:
                    idx_type = "unknown"

                index_info["indexes"].append({
                    "name": idx_name,
                    "type": idx_type,
                    "definition": idx_def
                })

                if index_info["primary_type"] is None:
                    index_info["primary_type"] = idx_type

            # Get chunk count for scale recommendation
            chunk_count = await conn.fetchval(
                "SELECT COUNT(*) FROM document_chunks"
            )

            index_info["chunk_count"] = chunk_count or 0
            index_info["scale_recommendation"] = self._get_scale_recommendation(chunk_count or 0)

            return index_info

    def _get_scale_recommendation(self, chunk_count: int) -> str:
        """Get recommendation based on vector count."""
        if chunk_count < 100000:
            return "Current scale is fine. HNSW is optimal for < 100K vectors."
        elif chunk_count < 1000000:
            return "Consider HNSW with optimized settings for 100K-1M vectors."
        elif chunk_count < 10000000:
            return "StreamingDiskANN recommended for 1M-10M vectors. Run create_streamingdiskann_index()."
        else:
            return "StreamingDiskANN required for 10M+ vectors. Run create_streamingdiskann_index() immediately."

    async def create_hnsw_index(
        self,
        m: int = 16,
        ef_construction: int = 64
    ) -> bool:
        """
        Create or recreate HNSW index with custom parameters.

        Good for up to ~10M vectors. For larger scale, use StreamingDiskANN.

        Args:
            m: Maximum number of connections per node (default: 16)
               Higher = better recall, more memory
            ef_construction: Size of dynamic candidate list during construction (default: 64)
                            Higher = better recall, slower build

        Returns:
            True if index created successfully
        """
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                # Drop existing indexes
                await conn.execute(
                    "DROP INDEX IF EXISTS document_chunks_embedding_idx"
                )
                await conn.execute(
                    "DROP INDEX IF EXISTS document_chunks_embedding_diskann_idx"
                )

                # Create HNSW index
                await conn.execute(
                    f"""
                    CREATE INDEX document_chunks_embedding_idx
                    ON document_chunks
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = {m}, ef_construction = {ef_construction})
                    """
                )

                logger.info(f"HNSW index created: m={m}, ef_construction={ef_construction}")
                return True

        except Exception as e:
            logger.error(f"Failed to create HNSW index: {e}")
            return False


# =============================================================================
# Convenience functions for common operations
# =============================================================================

_default_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create default vector store instance."""
    global _default_store

    if _default_store is None:
        _default_store = VectorStore()

    return _default_store


async def search_knowledge_base(
    query: str,
    limit: int = 10,
    min_similarity: float = 0.7
) -> List[SearchResult]:
    """
    Search the knowledge base for relevant content.

    Convenience wrapper for common search operations.

    Args:
        query: Natural language query
        limit: Maximum results
        min_similarity: Minimum similarity threshold

    Returns:
        List of SearchResult objects
    """
    store = get_vector_store()
    return await store.search(query, limit=limit, min_similarity=min_similarity)


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import sys

    async def main():
        store = VectorStore()

        if len(sys.argv) > 1 and sys.argv[1] == "stats":
            stats = await store.get_stats()
            print("Vector Store Statistics:")
            for k, v in stats.items():
                print(f"  {k}: {v}")

        elif len(sys.argv) > 2 and sys.argv[1] == "search":
            query = " ".join(sys.argv[2:])
            print(f"Searching for: {query}")
            results = await store.search(query, limit=5)

            for i, r in enumerate(results, 1):
                print(f"\n{i}. [{r.similarity:.3f}] {r.content[:200]}...")

        else:
            print("Usage:")
            print("  python vector_store.py stats    - Show statistics")
            print("  python vector_store.py search <query> - Search knowledge base")

        await store.close()

    asyncio.run(main())
