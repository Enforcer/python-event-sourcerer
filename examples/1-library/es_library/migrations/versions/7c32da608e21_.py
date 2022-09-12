"""empty message

Revision ID: 7c32da608e21
Revises: 6f9fbf30e41f
Create Date: 2022-09-11 13:31:29.558935

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7c32da608e21"
down_revision = "6f9fbf30e41f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("isbn", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("books")
    # ### end Alembic commands ###
