import requests
from typing import Optional, Dict, Any

OPENALEX_BASE_URL = "https://api.openalex.org"


def get_openalex_entities(
    entity_name: str,
    page: int = 1,
    per_page: int = 25,
    filter: Optional[str] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    mailto: Optional[str] = None,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Fetch a list of entities from the OpenAlex API.

    Parameters
    ----------
    entity_name : str
        Name of the entity (e.g. 'topics', 'works', 'authors', 'institutions')
    page : int
        Page number (default: 1)
    per_page : int
        Number of results per page (max 200)
    filter : str, optional
        OpenAlex filter string (e.g. 'field.id:F123')
    search : str, optional
        Free-text search query
    sort : str, optional
        Sort order (e.g. 'display_name:asc')
    mailto : str, optional
        Your email (recommended by OpenAlex for polite usage)
    timeout : int
        Request timeout in seconds

    Returns
    -------
    dict
        Parsed JSON response with keys: meta, results, group_by
    """

    url = f"{OPENALEX_BASE_URL}/{entity_name}"

    params = {
        "page": page,
        "per-page": per_page
    }

    if filter:
        params["filter"] = filter
    if search:
        params["search"] = search
    if sort:
        params["sort"] = sort
    if mailto:
        params["mailto"] = mailto

    headers = {
        "Accept": "application/json"
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=timeout
    )

    response.raise_for_status()  # raises HTTPError for 4xx/5xx

    return response.json()
