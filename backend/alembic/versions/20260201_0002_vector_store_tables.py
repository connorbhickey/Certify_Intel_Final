"""Add vector store tables for RAG pipeline

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-01

Creates tables for knowledge base document storage and vector search:
- knowledge_documents: Document metadata and deduplication
- document_chunks: Text chunks with pgvector embeddings
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create vector store tables."""

    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create knowledge_documents table
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(20), nullable=False),
        sa.Column('content_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('uploaded_by', sa.String(255), nullable=True),
        sa.Column('file_size_bytes', sa.Integer, default=0),
        sa.Column('chunk_count', sa.Integer, default=0),
        sa.Column('metadata', sa.JSON, default={}),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create document_chunks table with vector embedding
    op.execute('''
        CREATE TABLE document_chunks (
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
    ''')

    # Create HNSW index for fast vector search
    # ef_construction=128 and m=16 are good defaults for <1M vectors
    op.execute('''
        CREATE INDEX idx_document_chunks_embedding
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 128)
    ''')

    # Create indexes for common queries
    op.create_index('idx_documents_content_hash', 'knowledge_documents', ['content_hash'])
    op.create_index('idx_documents_file_type', 'knowledge_documents', ['file_type'])
    op.create_index('idx_chunks_document_id', 'document_chunks', ['document_id'])


def downgrade() -> None:
    """Remove vector store tables."""
    op.drop_table('document_chunks')
    op.drop_table('knowledge_documents')
    # Note: We don't drop the vector extension as other tables might use it
