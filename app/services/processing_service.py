"""Processing service: coordinates image-processing jobs and returns derived results."""

from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.processing.operations import ImageProcessor

logger = get_logger(__name__)


class ProcessingService:
    """Runs image-processing operations and returns derived results."""

    def __init__(self) -> None:
        self.processor = ImageProcessor()

    def available_operations(self) -> list[str]:
        return self.processor.available_operations()

    def apply_operation(
        self,
        array: Any,
        operation_name: str,
        **params: Any,
    ) -> dict[str, Any]:
        """Apply one operation to a NumPy array.

        Returns a dict with the result array, shape info, and operation record.
        """
        import numpy as np

        result, record = self.processor.apply(np.asarray(array), operation_name, **params)
        return {
            "result": result,
            "input_shape": record.input_shape,
            "output_shape": record.output_shape,
            "operation": record.to_dict(),
        }

    def apply_pipeline(
        self,
        array: Any,
        steps: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, Any]:
        """Apply a pipeline of operations."""
        import numpy as np

        result, records = self.processor.apply_pipeline(np.asarray(array), steps)
        return {
            "result": result,
            "input_shape": records[0].input_shape if records else None,
            "output_shape": records[-1].output_shape if records else None,
            "operations": [r.to_dict() for r in records],
        }

    def clear_history(self) -> None:
        self.processor.clear_history()
