"""
Helpers to build Microsoft Graph OData query strings from structured filters.
"""

from typing import Dict, Any, List, Optional


def build_search_query(
    search_text: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    parent_id: Optional[str] = None,
    owner: Optional[str] = None,
    mime_type: Optional[str] = None,
    modified_after: Optional[str] = None,
    modified_before: Optional[str] = None,
) -> str:
    """
    Build a Microsoft Graph search query or OData filter expression.

    Args:
        search_text: text to search (uses Graph $search parameter)
        filters: opaque filter dict (ignored if keys unsupported)
        parent_id: parent folder id
        owner: owner email/ID
        mime_type: MIME type filter
        modified_after: ISO8601 lower bound
        modified_before: ISO8601 upper bound

    Returns:
        Search text for $search parameter, or OData $filter expression
    """
    # For text search, Microsoft Graph uses $search parameter
    if search_text:
        return search_text

    # For filters, build OData $filter expression
    clauses: List[str] = []

    if parent_id:
        clauses.append(f"parentReference/id eq '{parent_id}'")
    if mime_type:
        clauses.append(f"file/mimeType eq '{mime_type}'")
    if modified_after:
        clauses.append(f"lastModifiedDateTime ge {modified_after}")
    if modified_before:
        clauses.append(f"lastModifiedDateTime le {modified_before}")

    # optional additional filters from dict
    if filters:
        for key, value in filters.items():
            if value is None:
                continue
            # Add support for common filter keys if needed

    return " and ".join(clauses) if clauses else ""
