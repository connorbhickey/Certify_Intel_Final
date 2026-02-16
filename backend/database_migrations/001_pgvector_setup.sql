-- Certify Intel v7.0 - PostgreSQL + pgvector Setup
-- This script runs automatically when PostgreSQL container starts
-- Creates vector extension and document chunks table for RAG

-- =============================================================================
-- STEP 1: Enable pgvector extension
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- Note: pgvectorscale requires separate installation on production
-- For development, pgvector provides sufficient functionality
-- pgvectorscale adds StreamingDiskANN for 10x+ performance at scale

-- =============================================================================
-- STEP 2: Create knowledge documents table (parent for chunks)
-- =============================================================================
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,  -- pdf, docx, txt, md
    content_hash TEXT UNIQUE NOT NULL,  -- SHA256 for deduplication
    chunk_count INTEGER DEFAULT 0,
    file_size_bytes BIGINT,
    uploaded_by TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_docs_content_hash ON knowledge_documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_docs_uploaded_by ON knowledge_documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_docs_file_type ON knowledge_documents(file_type);

-- =============================================================================
-- STEP 3: Create document chunks table with vector embeddings
-- =============================================================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    embedding vector(1536),  -- OpenAI text-embedding-3-small dimensions
    metadata JSONB DEFAULT '{}',  -- page_number, section, type, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- HNSW index for vector similarity search
-- This provides good performance for our scale (< 1M vectors)
-- For 50M+ vectors, use pgvectorscale's StreamingDiskANN instead
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (
    m = 16,              -- Max connections per node (default 16)
    ef_construction = 64  -- Size of dynamic candidate list (default 64)
);

-- B-tree indexes for filtering
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_token_count ON document_chunks(token_count);

-- GIN index for JSONB metadata queries
CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON document_chunks USING GIN (metadata);

-- =============================================================================
-- STEP 4: Create AI usage tracking table (cost monitoring)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ai_usage_log (
    id BIGSERIAL PRIMARY KEY,
    agent_type TEXT NOT NULL,  -- dashboard, discovery, battlecard, news, analytics, validation, records
    model TEXT NOT NULL,       -- gemini-2.0-flash, deepseek-v3.2, claude-opus-4.5, etc.
    task_type TEXT NOT NULL,   -- bulk_extraction, chat, analysis, strategy
    tokens_input INTEGER NOT NULL,
    tokens_output INTEGER NOT NULL,
    cost_usd DECIMAL(10, 6) NOT NULL,
    latency_ms INTEGER,
    user_id TEXT,
    competitor_id INTEGER,
    session_id TEXT,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for cost dashboard queries
CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON ai_usage_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_usage_agent ON ai_usage_log(agent_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_usage_model ON ai_usage_log(model, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_usage_daily ON ai_usage_log(DATE(timestamp), agent_type);
CREATE INDEX IF NOT EXISTS idx_usage_user ON ai_usage_log(user_id, timestamp DESC);

-- =============================================================================
-- STEP 5: Create daily cost summary view
-- =============================================================================
CREATE OR REPLACE VIEW daily_ai_costs AS
SELECT
    DATE(timestamp) as date,
    agent_type,
    model,
    SUM(tokens_input) as total_tokens_input,
    SUM(tokens_output) as total_tokens_output,
    SUM(cost_usd) as total_cost_usd,
    COUNT(*) as request_count,
    AVG(latency_ms) as avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms
FROM ai_usage_log
GROUP BY DATE(timestamp), agent_type, model;

-- =============================================================================
-- STEP 6: Create LangGraph checkpoints table (agent state persistence)
-- =============================================================================
CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_parent
ON langgraph_checkpoints(thread_id, checkpoint_ns, parent_checkpoint_id);

CREATE INDEX IF NOT EXISTS idx_checkpoints_created
ON langgraph_checkpoints(created_at DESC);

-- =============================================================================
-- STEP 7: Create vector search function (helper for Python)
-- =============================================================================
CREATE OR REPLACE FUNCTION search_similar_chunks(
    query_embedding vector(1536),
    match_count INTEGER DEFAULT 10,
    min_similarity FLOAT DEFAULT 0.7,
    filter_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
    chunk_id BIGINT,
    document_id TEXT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id as chunk_id,
        dc.document_id,
        dc.content,
        dc.metadata,
        (1 - (dc.embedding <=> query_embedding))::FLOAT as similarity
    FROM document_chunks dc
    WHERE
        (filter_metadata IS NULL OR dc.metadata @> filter_metadata)
        AND (1 - (dc.embedding <=> query_embedding)) >= min_similarity
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 8: Create cost tracking function
-- =============================================================================
CREATE OR REPLACE FUNCTION get_daily_budget_usage(
    check_date DATE DEFAULT CURRENT_DATE,
    daily_budget DECIMAL DEFAULT 50.0
)
RETURNS TABLE (
    total_spent DECIMAL,
    remaining_budget DECIMAL,
    percent_used DECIMAL,
    request_count BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(SUM(cost_usd), 0)::DECIMAL as total_spent,
        (daily_budget - COALESCE(SUM(cost_usd), 0))::DECIMAL as remaining_budget,
        (COALESCE(SUM(cost_usd), 0) / daily_budget * 100)::DECIMAL as percent_used,
        COUNT(*)::BIGINT as request_count
    FROM ai_usage_log
    WHERE DATE(timestamp) = check_date;
END;
$$;

-- =============================================================================
-- DONE: Database initialized with pgvector support
-- =============================================================================
-- Next steps:
-- 1. Run Alembic migrations to create application tables
-- 2. Configure .env with PostgreSQL connection string
-- 3. Start the backend with: python main.py
-- =============================================================================
