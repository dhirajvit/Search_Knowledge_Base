"""Create semantic_cache table

Revision ID: 0003
Revises: 0002
Create Date: 2025-02-23

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS semantic_cache (
            id SERIAL PRIMARY KEY,
            question_embedding vector(1024) NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS semantic_cache_embedding_idx
        ON semantic_cache USING hnsw (question_embedding vector_cosine_ops);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS semantic_cache CASCADE;")
