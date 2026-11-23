"""Wave 2 specification persistence models matching migration 009."""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from devflow_api.models.base import Base, UTCDateTime


class UTCTextDateTime(TypeDecorator[datetime]):
    """Store aware UTC timestamps in the migration's ISO 8601 TEXT columns."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("UTCTextDateTime requires an aware datetime")
        return value.astimezone(UTC).isoformat()

    def process_result_value(self, value: str | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        timestamp = datetime.fromisoformat(value)
        return (
            timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp.astimezone(UTC)
        )


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SpecificationRequest(Base):
    __tablename__ = "specification_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','generating','generated','under_review',"
            " 'revision_required','ready_for_approval','approved','cancelled')"
        ),
        Index("idx_spec_req_status", "status"),
        Index("idx_spec_req_workflow_run_id", "workflow_run_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    business_goal: Mapped[str | None] = mapped_column(Text)
    functional_requirements: Mapped[str | None] = mapped_column(Text)
    nonfunctional_constraints: Mapped[str | None] = mapped_column(Text)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text)
    repo_context: Mapped[str | None] = mapped_column(Text)
    clarifying_questions: Mapped[str | None] = mapped_column(Text)
    workflow_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_runs.id", ondelete="SET NULL")
    )
    workflow_step_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_step_runs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"))
    current_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    content_hash: Mapped[str] = mapped_column(Text)
    provider_id: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow, onupdate=_utcnow)


class SpecificationApprovalRequest(Base):
    __tablename__ = "specification_approval_requests"
    __table_args__ = (
        Index("idx_spec_approval_version_id", "specification_version_id"),
        Index("idx_spec_approval_expires_at", "expires_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    specification_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specification_versions.id", ondelete="CASCADE")
    )
    operation: Mapped[str] = mapped_column(Text, server_default=text("'approve_specification'"))
    parameters_hash: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=text("CURRENT_TIMESTAMP"), default=_utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    rejected_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class SpecificationVersion(Base):
    __tablename__ = "specification_versions"
    __table_args__ = (
        UniqueConstraint("specification_request_id", "version_number"),
        CheckConstraint(
            "status IN ('draft','generated','under_review','revision_required',"
            " 'ready_for_approval','approved','cancelled')"
        ),
        Index("idx_spec_ver_request_id", "specification_request_id"),
        Index("idx_spec_ver_status", "status"),
        Index("idx_spec_ver_standalone_approval_id", "spec_standalone_approval_id"),
        Index("idx_spec_ver_bound_approval_id", "spec_bound_approval_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    specification_request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specification_requests.id", ondelete="CASCADE")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"))
    content_digest: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(UTCTextDateTime)
    approved_by: Mapped[str | None] = mapped_column(Text)
    spec_standalone_approval_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("specification_approval_requests.id", ondelete="SET NULL", use_alter=True),
    )
    spec_bound_approval_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("approval_requests.id", ondelete="SET NULL")
    )
    supersedes_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("specification_versions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow, onupdate=_utcnow)


class SpecificationArtifact(Base):
    __tablename__ = "specification_artifacts"
    __table_args__ = (
        UniqueConstraint("specification_version_id", "artifact_type"),
        CheckConstraint("artifact_type IN ('requirements','design','tasks')"),
        Index("idx_spec_art_version_id", "specification_version_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    specification_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specification_versions.id", ondelete="CASCADE")
    )
    artifact_type: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow)


class GenerationAttempt(Base):
    __tablename__ = "generation_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('pending','running','succeeded','failed','cancelled')"),
        Index("idx_gen_attempt_request_id", "specification_request_id"),
        Index("idx_gen_attempt_status", "status"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    specification_request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specification_requests.id", ondelete="CASCADE")
    )
    specification_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("specification_versions.id", ondelete="SET NULL")
    )
    provider_id: Mapped[str] = mapped_column(Text)
    model_id: Mapped[str] = mapped_column(Text)
    prompt_hash: Mapped[str] = mapped_column(Text)
    context_truncated: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cancellation_requested: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    started_at: Mapped[datetime | None] = mapped_column(UTCTextDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCTextDateTime)
    token_usage_json: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow, onupdate=_utcnow)


class ReviewAttempt(Base):
    __tablename__ = "review_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('pending','running','succeeded','failed','cancelled')"),
        Index("idx_review_attempt_version_id", "specification_version_id"),
        Index("idx_review_attempt_status", "status"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    specification_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specification_versions.id", ondelete="CASCADE")
    )
    provider_id: Mapped[str] = mapped_column(Text)
    model_id: Mapped[str] = mapped_column(Text)
    artifact_hash: Mapped[str] = mapped_column(Text)
    cancellation_requested: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    started_at: Mapped[datetime | None] = mapped_column(UTCTextDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCTextDateTime)
    finding_count_by_severity: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow, onupdate=_utcnow)


class ReviewFinding(Base):
    __tablename__ = "review_findings"
    __table_args__ = (
        CheckConstraint("source IN ('deterministic','ai')"),
        CheckConstraint("severity IN ('Critical','High','Medium','Low','Informational')"),
        Index("idx_review_finding_version_id", "specification_version_id"),
        Index("idx_review_finding_severity", "severity"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_attempt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("review_attempts.id", ondelete="CASCADE")
    )
    specification_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specification_versions.id", ondelete="CASCADE")
    )
    severity: Mapped[str] = mapped_column(Text)
    dimension: Mapped[str] = mapped_column(Text)
    finding_text: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    acknowledged_by: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCTextDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCTextDateTime, default=_utcnow)
