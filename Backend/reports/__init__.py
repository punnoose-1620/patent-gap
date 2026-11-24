"""
Patent Gap PDF report framework.

Public builders (return PDF bytes):

- ``build_patent_vs_infringement_report(case_id, infringement_id)``
- ``build_products_patents_infringements_report(case_id, hit_kind=...)``
- ``build_whats_new_report(user_id, folder_id=...)``
"""

from reports.builders import (
    build_patent_vs_infringement_report,
    build_products_patents_infringements_report,
    build_whats_new_report,
)

__all__ = [
    'build_patent_vs_infringement_report',
    'build_products_patents_infringements_report',
    'build_whats_new_report',
]
