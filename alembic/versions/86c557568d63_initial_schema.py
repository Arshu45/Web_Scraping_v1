"""initial_schema

Revision ID: 86c557568d63
Revises: 
Create Date: 2026-04-22 10:28:35.805751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '86c557568d63'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables from scratch on a clean database."""

    # 1. categories (no foreign keys, must be first)
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # 2. competitors (no foreign keys)
    op.create_table(
        'competitors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # 3. scraping_sources (FK → competitors)
    op.create_table(
        'scraping_sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('competitor_id', sa.Integer(), nullable=False),
        sa.Column('source_name', sa.String(length=50), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('spider_name', sa.String(length=50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('modified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['competitor_id'], ['competitors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_url'),
    )

    # 4. scraping_runs (no foreign keys)
    op.create_table(
        'scraping_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('spider_name', sa.String(length=50), nullable=False),
        sa.Column('prefect_run_id', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('items_scraped', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('items_inserted', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('items_updated', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='running'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 5. promotions (FK → competitors, categories)
    op.create_table(
        'promotions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('competitor_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('offer_title', sa.Text(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('promo_type', sa.String(length=30), nullable=True),
        sa.Column('discount_min', sa.Float(), nullable=True),
        sa.Column('discount_max', sa.Float(), nullable=True),
        sa.Column('flat_value', sa.Float(), nullable=True),
        sa.Column('min_purchase', sa.Float(), nullable=True),
        sa.Column('coupon_code', sa.String(length=50), nullable=True),
        sa.Column('user_type', sa.String(length=20), nullable=True),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('source_name', sa.String(length=50), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('offer_hash', sa.String(length=64), nullable=False),
        sa.Column('scraped_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['competitor_id'], ['competitors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('offer_hash'),
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table('promotions')
    op.drop_table('scraping_runs')
    op.drop_table('scraping_sources')
    op.drop_table('competitors')
    op.drop_table('categories')
