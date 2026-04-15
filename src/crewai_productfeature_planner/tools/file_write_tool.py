"""File write tool for persisting PRD documents with versioning."""

import os
from datetime import datetime
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


class PRDFileWriteInput(BaseModel):
    """Input schema for PRDFileWriteTool."""

    content: str = Field(..., description="The PRD content to write to file.")
    filename: str = Field(
        default="",
        description="Optional filename. If empty, a timestamped name is generated.",
    )
    version: int = Field(
        default=1,
        description="Version number of the PRD.",
    )


class PRDFileWriteTool(BaseTool):
    """Saves PRD documents to disk with automatic versioning.

    Files are organised into year/month subdirectories under the base
    output directory:  ``output/prds/YYYY/MM/prd_vN_YYYYMMDD_HHMMSS.md``.
    """

    name: str = "prd_file_writer"
    description: str = (
        "Saves a PRD document to the output directory with versioning. "
        "Use this tool to persist PRD drafts and final versions to disk."
    )
    args_schema: Type[BaseModel] = PRDFileWriteInput
    output_dir: str = "output/prds"

    def _run(self, content: str, filename: str = "", version: int = 1) -> str:
        now = datetime.now()
        # Build year/month subdirectory: YYYY/MM
        sub_dir = now.strftime("%Y") + "/" + now.strftime("%m")
        output_path = Path(self.output_dir) / sub_dir
        output_path.mkdir(parents=True, exist_ok=True)

        if not filename:
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            filename = f"prd_v{version}_{timestamp}.md"
        elif not filename.endswith(".md"):
            filename = f"{filename}.md"

        filepath = output_path / filename
        filepath.write_text(content, encoding="utf-8")
        logger.info("PRD saved to %s (%d bytes)", filepath, len(content))
        logger.debug("PRD file details — version=%d, dir=%s", version, self.output_dir)

        # Also upload to GCS when configured
        try:
            from crewai_productfeature_planner.tools.output_storage import (
                _gcs_bucket_name,
                _write_to_gcs,
            )
            bucket = _gcs_bucket_name()
            if bucket:
                relative_path = f"prds/{sub_dir}/{filename}"
                _write_to_gcs(bucket, relative_path, content)
        except Exception:  # noqa: BLE001
            pass  # GCS is best-effort; local write already succeeded

        return f"PRD saved to {filepath}"
