"""create files table

Revision ID: 212e86297f03
Revises: 
Create Date: 2026-09-13 11:12:58.529912

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '212e86297f03'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("bit_depth", sa.Integer(), nullable=False),
        sa.Column("codec", sa.String(), nullable=False),
        sa.Column("sample_format", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_files_name", "files", ["name"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_files_name", table_name="files")
    op.drop_table("files")
