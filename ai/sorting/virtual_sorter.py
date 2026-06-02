"""
Virtual sorting logic for scanned medicines.
Determines bin placement based on name and expiration date.
Designed for future robotic arm integration.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SortResult:
    status: str             # valid | expired | unknown
    sort_category: str      # valid_medicine | expired_medicine | missing_data
    recommended_action: str # place_in_bin_A | place_in_bin_B | keep_scanning


def sort_medicine(medicine_name: str, expiration_date: Optional[str]) -> SortResult:
    """
    Classify a scanned medicine for sorting.

    Args:
        medicine_name:   Identified name, or "unknown" if not found.
        expiration_date: Normalized "MM/YYYY", or None if not found.

    Returns:
        SortResult with status, category, and recommended action.
    """
    if medicine_name == "unknown" or expiration_date is None:
        return SortResult(
            status="unknown",
            sort_category="missing_data",
            recommended_action="keep_scanning",
        )

    try:
        month, year = map(int, expiration_date.split("/"))
        exp_date = datetime(year, month, 1)
        now = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if exp_date < now:
            return SortResult(
                status="expired",
                sort_category="expired_medicine",
                recommended_action="place_in_bin_B",
            )
        return SortResult(
            status="valid",
            sort_category="valid_medicine",
            recommended_action="place_in_bin_A",
        )

    except (ValueError, AttributeError):
        return SortResult(
            status="unknown",
            sort_category="missing_data",
            recommended_action="keep_scanning",
        )
