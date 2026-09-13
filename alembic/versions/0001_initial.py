"""initial schema"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("api_keys", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("prefix", sa.String(32), nullable=False, unique=True), sa.Column("digest", sa.LargeBinary(32), nullable=False, unique=True), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("rate_limit_rpm", sa.Integer(), nullable=False, server_default="60"), sa.Column("monthly_quota", sa.Integer(), nullable=False, server_default="10000"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("jobs", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("api_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_keys.id"), nullable=False), sa.Column("job_type", sa.String(16), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="queued"), sa.Column("request", postgresql.JSONB(), nullable=False), sa.Column("result_summary", postgresql.JSONB()), sa.Column("error_code", sa.String(64)), sa.Column("error_message", sa.Text()), sa.Column("progress", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("duration_ms", sa.Integer()))
    op.create_table("scrape_results", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id")), sa.Column("url", sa.Text(), nullable=False), sa.Column("final_url", sa.Text(), nullable=False), sa.Column("status_code", sa.Integer(), nullable=False), sa.Column("title", sa.Text()), sa.Column("html", sa.Text()), sa.Column("markdown", sa.Text()), sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"), sa.Column("scraping_method", sa.String(16), nullable=False), sa.Column("duration_ms", sa.Integer(), nullable=False), sa.Column("html_truncated", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("markdown_truncated", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

def downgrade() -> None:
    op.drop_table("scrape_results")
    op.drop_table("jobs")
    op.drop_table("api_keys")
