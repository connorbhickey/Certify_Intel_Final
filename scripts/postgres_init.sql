-- =============================================================================
-- Certify Intel - PostgreSQL Initialization Script
-- =============================================================================
-- Runs automatically on first container start via docker-entrypoint-initdb.d
-- Enables pgvector extension and creates the vector search tables
-- (ORM-managed tables are created by SQLAlchemy on app startup)
-- =============================================================================

-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Knowledge documents table (used by vector_store.py)
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(50),
    content_hash VARCHAR(64) UNIQUE,
    uploaded_by VARCHAR(255),
    file_size_bytes INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Document chunks with vector embeddings (used by vector_store.py)
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(36) REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- HNSW index for fast approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Supporting indexes
CREATE INDEX IF NOT EXISTS idx_knowledge_documents_hash ON knowledge_documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks(document_id);
