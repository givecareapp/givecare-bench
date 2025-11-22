"""Compatibility shim for report generation.

Re-exports ReportGenerator from the export package under the
evaluation namespace for test compatibility.
"""

from invisiblebench.export.reports import ReportGenerator

__all__ = ["ReportGenerator"]

