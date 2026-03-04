"""GET /api/reports — list and retrieve saved reports."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from superpowers.reporting import ReportRegistry

router = APIRouter()


def _get_registry() -> ReportRegistry:
    return ReportRegistry()


@router.get("/reports")
def list_reports(limit: int = 50):
    """Return saved reports (most recent first)."""
    registry = _get_registry()
    return registry.list_reports(limit=limit)


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    """Return a single report as JSON."""
    registry = _get_registry()
    report = registry.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")
    return report.to_dict()
