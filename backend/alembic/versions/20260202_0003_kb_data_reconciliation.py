"""Add KB data reconciliation tables and extend existing tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-02

Creates new tables and extends existing ones for KB data reconciliation:
- kb_entity_links: Links KB documents to competitor entities
- kb_data_extractions: Structured data extracted from KB documents
- Extends knowledge_base table with new columns
- Extends data_sources table with KB reconciliation columns
- Extends knowledge_documents table with temporal tracking
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create KB reconciliation tables and extend existing tables."""

    # =========================================================================
    # 1. Extend knowledge_base table (existing SQLite table)
    # =========================================================================
    # Note: SQLite has limited ALTER TABLE support, so we add columns one at a time

    # Add new columns to knowledge_base table
    op.add_column('knowledge_base', sa.Column('content_type', sa.String(50), nullable=True))
    op.add_column('knowledge_base', sa.Column('category', sa.String(100), nullable=True))
    op.add_column('knowledge_base', sa.Column('tags', sa.Text, nullable=True))
    op.add_column('knowledge_base', sa.Column('source', sa.String(500), nullable=True))
    op.add_column('knowledge_base', sa.Column('extra_metadata', sa.Text, nullable=True))
    op.add_column('knowledge_base', sa.Column('document_date', sa.DateTime, nullable=True))
    op.add_column('knowledge_base', sa.Column('data_as_of_date', sa.DateTime, nullable=True))
    op.add_column('knowledge_base', sa.Column('document_type', sa.String(50), server_default='upload'))
    op.add_column('knowledge_base', sa.Column('linked_competitor_ids', sa.Text, nullable=True))
    op.add_column('knowledge_base', sa.Column('extraction_status', sa.String(20), server_default='pending'))
    op.add_column('knowledge_base', sa.Column('content_hash', sa.String(64), nullable=True))

    # Create index on content_hash for deduplication
    op.create_index('idx_kb_content_hash', 'knowledge_base', ['content_hash'])

    # =========================================================================
    # 2. Extend knowledge_documents table (PostgreSQL pgvector table)
    # =========================================================================
    # Add temporal and linking columns
    op.add_column('knowledge_documents', sa.Column('document_date', sa.DateTime, nullable=True))
    op.add_column('knowledge_documents', sa.Column('data_as_of_date', sa.DateTime, nullable=True))
    op.add_column('knowledge_documents', sa.Column('document_type', sa.String(50), server_default='upload'))
    op.add_column('knowledge_documents', sa.Column('linked_competitor_ids', sa.Text, nullable=True))
    op.add_column('knowledge_documents', sa.Column('extraction_status', sa.String(20), server_default='pending'))

    # =========================================================================
    # 3. Extend data_sources table with KB reconciliation columns
    # =========================================================================
    op.add_column('data_sources', sa.Column('kb_document_id', sa.String(36), nullable=True))
    op.add_column('data_sources', sa.Column('kb_item_id', sa.Integer, nullable=True))
    op.add_column('data_sources', sa.Column('kb_chunk_id', sa.Integer, nullable=True))
    op.add_column('data_sources', sa.Column('kb_extraction_id', sa.Integer, nullable=True))
    op.add_column('data_sources', sa.Column('reconciliation_status', sa.String(20), nullable=True))
    op.add_column('data_sources', sa.Column('conflict_details', sa.Text, nullable=True))

    # =========================================================================
    # 4. Create kb_entity_links table
    # =========================================================================
    op.create_table(
        'kb_entity_links',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.String(36), nullable=True),  # Links to knowledge_documents
        sa.Column('kb_item_id', sa.Integer, sa.ForeignKey('knowledge_base.id'), nullable=True),
        sa.Column('chunk_id', sa.Integer, nullable=True),
        sa.Column('competitor_id', sa.Integer, sa.ForeignKey('competitors.id'), nullable=False),
        sa.Column('link_type', sa.String(20), server_default='inferred'),
        sa.Column('link_confidence', sa.Float, server_default='0.0'),
        sa.Column('extracted_entities', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('validated_by', sa.String(255), nullable=True),
        sa.Column('validated_at', sa.DateTime, nullable=True),
    )

    # Create indexes for common queries
    op.create_index('idx_kb_entity_links_document', 'kb_entity_links', ['document_id'])
    op.create_index('idx_kb_entity_links_kb_item', 'kb_entity_links', ['kb_item_id'])
    op.create_index('idx_kb_entity_links_competitor', 'kb_entity_links', ['competitor_id'])

    # =========================================================================
    # 5. Create kb_data_extractions table
    # =========================================================================
    op.create_table(
        'kb_data_extractions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.String(36), nullable=True),  # Links to knowledge_documents
        sa.Column('kb_item_id', sa.Integer, sa.ForeignKey('knowledge_base.id'), nullable=True),
        sa.Column('chunk_id', sa.Integer, nullable=True),
        sa.Column('competitor_id', sa.Integer, sa.ForeignKey('competitors.id'), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('extracted_value', sa.String(500), nullable=False),
        sa.Column('extraction_context', sa.Text, nullable=True),
        sa.Column('extraction_confidence', sa.Float, server_default='0.0'),
        sa.Column('extraction_method', sa.String(50), server_default='gpt_extraction'),
        sa.Column('data_as_of_date', sa.DateTime, nullable=True),
        sa.Column('document_date', sa.DateTime, nullable=True),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('reconciliation_note', sa.Text, nullable=True),
        sa.Column('verified_by', sa.String(255), nullable=True),
        sa.Column('verified_at', sa.DateTime, nullable=True),
        sa.Column('data_source_id', sa.Integer, sa.ForeignKey('data_sources.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Create indexes for common queries
    op.create_index('idx_kb_extractions_document', 'kb_data_extractions', ['document_id'])
    op.create_index('idx_kb_extractions_kb_item', 'kb_data_extractions', ['kb_item_id'])
    op.create_index('idx_kb_extractions_competitor', 'kb_data_extractions', ['competitor_id'])
    op.create_index('idx_kb_extractions_field', 'kb_data_extractions', ['field_name'])
    op.create_index('idx_kb_extractions_status', 'kb_data_extractions', ['status'])


def downgrade() -> None:
    """Remove KB reconciliation tables and columns."""

    # Drop new tables
    op.drop_table('kb_data_extractions')
    op.drop_table('kb_entity_links')

    # Remove columns from data_sources
    op.drop_column('data_sources', 'kb_document_id')
    op.drop_column('data_sources', 'kb_item_id')
    op.drop_column('data_sources', 'kb_chunk_id')
    op.drop_column('data_sources', 'kb_extraction_id')
    op.drop_column('data_sources', 'reconciliation_status')
    op.drop_column('data_sources', 'conflict_details')

    # Remove columns from knowledge_documents
    op.drop_column('knowledge_documents', 'document_date')
    op.drop_column('knowledge_documents', 'data_as_of_date')
    op.drop_column('knowledge_documents', 'document_type')
    op.drop_column('knowledge_documents', 'linked_competitor_ids')
    op.drop_column('knowledge_documents', 'extraction_status')

    # Remove columns from knowledge_base
    op.drop_index('idx_kb_content_hash', 'knowledge_base')
    op.drop_column('knowledge_base', 'content_type')
    op.drop_column('knowledge_base', 'category')
    op.drop_column('knowledge_base', 'tags')
    op.drop_column('knowledge_base', 'source')
    op.drop_column('knowledge_base', 'extra_metadata')
    op.drop_column('knowledge_base', 'document_date')
    op.drop_column('knowledge_base', 'data_as_of_date')
    op.drop_column('knowledge_base', 'document_type')
    op.drop_column('knowledge_base', 'linked_competitor_ids')
    op.drop_column('knowledge_base', 'extraction_status')
    op.drop_column('knowledge_base', 'content_hash')
