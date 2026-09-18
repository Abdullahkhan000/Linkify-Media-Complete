"""Small dependency-light client for Linkify Media API v1."""

import requests


class LinkifyClient:
    def __init__(self, api_key, base_url="http://localhost:8000", timeout=30):
        if not api_key:
            raise ValueError("api_key is required")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key, "Accept": "application/json"})

    def _request(self, method, path, **kwargs):
        response = self.session.request(
            method, f"{self.base_url}/api/v1/{path.lstrip('/')}", timeout=self.timeout, **kwargs
        )
        response.raise_for_status()
        return response.json()

    def search(self, query, media_type="movie", country="us", fields=None):
        params = {"q": query, "type": media_type, "country": country}
        if fields:
            params["fields"] = ",".join(fields) if isinstance(fields, (list, tuple)) else fields
        return self._request("GET", "search/", params=params)

    def search_results(self, query, media_type="movie", page=1, **filters):
        return self._request(
            "GET", "search/results/",
            params={"q": query, "type": media_type, "page": page, **filters},
        )

    def details(self, media_type, media_id, country="US"):
        return self._request("GET", f"media/{media_type}/{media_id}/", params={"country": country})

    def trending(self, media_type="all"):
        return self._request("GET", "trending/", params={"type": media_type})

    def search_people(self, query):
        return self._request("GET", "people/search/", params={"q": query})

    def batch(self, items):
        return self._request("POST", "batch/", json={"items": items})

    def usage(self):
        return self._request("GET", "usage/")
