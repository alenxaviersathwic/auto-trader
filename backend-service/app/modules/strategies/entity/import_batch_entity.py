from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class ImportBatch(BaseEntity):
    """
    Import batch log entity.
    """

    __tablename__ = "import_batches"

    fileName: Mapped[str] = mapped_column("file_name", String(255), nullable=False)
    sourceFormat: Mapped[str] = mapped_column("source_format", String(20), nullable=False)
    mode: Mapped[str] = mapped_column("mode", String(10), nullable=False, default="SKIP")
    dryRun: Mapped[bool] = mapped_column("dry_run", Boolean, nullable=False, default=False)
    totalItems: Mapped[int] = mapped_column("total_items", Integer, nullable=False, default=0)
    createdCount: Mapped[int] = mapped_column("created_count", Integer, nullable=False, default=0)
    updatedCount: Mapped[int] = mapped_column("updated_count", Integer, nullable=False, default=0)
    skippedCount: Mapped[int] = mapped_column("skipped_count", Integer, nullable=False, default=0)
    failedCount: Mapped[int] = mapped_column("failed_count", Integer, nullable=False, default=0)
    errors: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column("errors", JSONB, nullable=True)
    warnings: Mapped[Optional[List[Any]]] = mapped_column("warnings", JSONB, nullable=True)
