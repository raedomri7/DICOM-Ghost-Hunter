"""SQLAlchemy ORM models for the analysis database.

The schema is normalized and deliberately avoids storing patient-identifying
information (names, birth dates, etc.) beyond what is needed for identification
and which the user has chosen to retain.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    configuration: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    examinations: Mapped[list[Examination]] = relationship(
        "Examination", back_populates="session", cascade="all, delete-orphan"
    )
    findings: Mapped[list[QCFinding]] = relationship(
        "QCFinding", back_populates="session", cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(
        "Report", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_analysis_sessions_started_at", "started_at"),
        Index("ix_analysis_sessions_status", "status"),
    )


class Examination(Base):
    __tablename__ = "examinations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    study_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    modality: Mapped[str | None] = mapped_column(String(16), nullable=True)
    study_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    study_description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    series_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    instance_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    session: Mapped[AnalysisSession] = relationship("AnalysisSession", back_populates="examinations")
    series: Mapped[list[Series]] = relationship(
        "Series", back_populates="examination", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_examinations_study_instance_uid", "study_instance_uid"),
        Index("ix_examinations_modality", "modality"),
    )


class Series(Base):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    examination_id: Mapped[str] = mapped_column(
        ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    modality: Mapped[str | None] = mapped_column(String(16), nullable=True)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    instance_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    examination: Mapped[Examination] = relationship("Examination", back_populates="series")

    __table_args__ = (
        Index("ix_series_series_instance_uid", "series_instance_uid"),
    )


class QCFinding(Base):
    __tablename__ = "qc_findings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    examination_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    series_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    instance_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    dicom_tags: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[AnalysisSession] = relationship("AnalysisSession", back_populates="findings")

    __table_args__ = (
        Index("ix_qc_findings_category_severity", "category", "severity"),
        Index("ix_qc_findings_created_at", "created_at"),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    file_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    report_type: Mapped[str] = mapped_column(String(32), default="pdf", nullable=False)

    session: Mapped[AnalysisSession] = relationship("AnalysisSession", back_populates="reports")


# Aliases kept for compatibility with domain-layer references.
models: dict[str, Any] = {
    "AnalysisSession": AnalysisSession,
    "Examination": Examination,
    "Series": Series,
    "QCFinding": QCFinding,
    "Report": Report,
}
