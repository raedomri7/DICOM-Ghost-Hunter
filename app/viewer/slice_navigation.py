"""Slice navigation logic for multi-slice DICOM series."""

from __future__ import annotations

from typing import Any

from app.dicom.reader import DICOMReader


class SliceNavigator:
    """Navigates the slices of a DICOM series.

    Holds references to instances (sorted by slice position) and provides
    previous / next / jump-to-index navigation. Pixel arrays are loaded on
    demand via DICOMReader.load_pixel_array to keep memory usage low.
    """

    def __init__(self, instances: list[Any]) -> None:
        # Sort instances by ImagePositionPatient projected onto slice normal if
        # available, otherwise by SOPInstanceUID for stable ordering.
        self.instances = self._sort_instances(instances)
        self._index = 0
        self.reader = DICOMReader()
        self._pixel_cache: dict[int, Any] = {}

    # ------------------------------------------------------------------ #
    def _sort_instances(self, instances: list[Any]) -> list[Any]:
        """Order slices by spatial position along the slice normal."""
        if not instances:
            return instances

        from app.dicom.geometry import (
            compute_slice_normal,
            direction_cosines,
            project_position,
        )

        # Use the first instance's orientation as the series reference.
        first_iop = instances[0].image_orientation_patient
        normal = None
        if first_iop and len(first_iop) == 6:
            rc = direction_cosines(first_iop)
            if rc is not None:
                row, col = rc
                normal = compute_slice_normal(row, col)

        def sort_key(inst: Any) -> tuple:
            ipp = inst.image_position_patient
            if normal is not None and ipp and len(ipp) == 3:
                pos = project_position(ipp, normal)
                if pos is not None:
                    return (0.0, pos)
            # Fallback: stable sort by SOPInstanceUID.
            return (1.0, str(inst.sop_instance_uid or ""))

        return sorted(instances, key=sort_key)

    # ------------------------------------------------------------------ #
    @property
    def count(self) -> int:
        return len(self.instances)

    @property
    def index(self) -> int:
        return self._index

    @property
    def current_instance(self) -> Any | None:
        if not self.instances:
            return None
        return self.instances[self._index]

    def set_index(self, index: int) -> None:
        if not self.instances:
            return
        self._index = max(0, min(index, len(self.instances) - 1))
        self._pixel_cache.clear()

    def next_slice(self) -> Any | None:
        if not self.instances:
            return None
        self._index = min(self._index + 1, len(self.instances) - 1)
        return self.current_instance

    def previous_slice(self) -> Any | None:
        if not self.instances:
            return None
        self._index = max(self._index - 1, 0)
        return self.current_instance

    # ------------------------------------------------------------------ #
    def get_current_array(self) -> Any | None:
        """Return the decoded pixel array for the current slice (cached)."""
        if not self.instances:
            return None
        inst = self.current_instance
        if inst is None:
            return None
        if self._index in self._pixel_cache:
            return self._pixel_cache[self._index]

        array = self.reader.load_pixel_array(inst.file_path)
        if array is not None:
            self._pixel_cache[self._index] = array
        return array

    def get_slice_label(self) -> str:
        if not self.instances:
            return "No slices"
        inst = self.current_instance
        if inst is None:
            return "No slices"
        sop = inst.sop_instance_uid or "?"
        pos = inst.image_position_patient
        pos_str = ""
        if pos and len(pos) == 3:
            pos_str = f" | IPP=({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})"
        return f"Slice {self._index + 1}/{len(self.instances)} | {sop}{pos_str}"

    def clear_cache(self) -> None:
        self._pixel_cache.clear()
