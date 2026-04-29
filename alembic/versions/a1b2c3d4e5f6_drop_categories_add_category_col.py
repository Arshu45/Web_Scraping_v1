"""drop_categories_table_add_category_column

Revision ID: a1b2c3d4e5f6
Revises: 86c557568d63
Create Date: 2026-04-27

Changes:
  - DROP categories table
  - REMOVE category_id FK from promotions
  - ADD category VARCHAR(100) column to promotions
  - REMOVE category column from competitors (was a flat string, now unused)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '86c557568d63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the FK constraint and category_id column from promotions
    op.drop_constraint('promotions_category_id_fkey', 'promotions', type_='foreignkey')
    op.drop_column('promotions', 'category_id')

    # 2. Add the new flat category column to promotions
    op.add_column('promotions',
        sa.Column('category', sa.String(length=100), nullable=True)
    )

    # 3. Drop the category column from competitors (was unused after this refactor)
    op.drop_column('competitors', 'category')

    # 4. Drop the categories table (no longer needed)
    op.drop_table('categories')


def downgrade() -> None:
    # Recreate categories table
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # Restore category column on competitors
    op.add_column('competitors',
        sa.Column('category', sa.String(length=50), nullable=True)
    )

    # Remove flat category column from promotions
    op.drop_column('promotions', 'category')

    # Restore category_id FK on promotions
    op.add_column('promotions',
        sa.Column('category_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'promotions_category_id_fkey',
        'promotions', 'categories',
        ['category_id'], ['id']
    )
