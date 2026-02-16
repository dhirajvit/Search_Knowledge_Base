"""Create session and conversations tables

Revision ID: 0002
Revises: 0001
Create Date: 2025-02-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            session_id VARCHAR(36) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS user_sessions_user_id_idx
        ON user_sessions (user_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS user_sessions_session_id_idx
        ON user_sessions (session_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR(36) NOT NULL REFERENCES user_sessions(session_id),
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources JSONB DEFAULT '[]',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS conversations_session_id_idx
        ON conversations (session_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversations CASCADE;")
    op.execute("DROP TABLE IF EXISTS user_sessions CASCADE;")
