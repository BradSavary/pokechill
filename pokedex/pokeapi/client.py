"""
HTTP client for PokéAPI with a local disk cache.

Every JSON response is saved under the cache directory, so the API is only
called once per resource: re-running the import is fast, works offline and
is polite to a free community service.
"""

import json
from pathlib import Path

import httpx

BASE_URL = "https://pokeapi.co/api/v2/"


def id_from_url(url: str) -> int:
    """Extract the numeric id from a PokéAPI URL (".../evolution-chain/10/" -> 10)."""
    return int(url.rstrip("/").rsplit("/", 1)[1])


class PokeAPIClient:
    def __init__(self, cache_dir: Path, http: httpx.Client):
        self.cache_dir = cache_dir
        # The httpx client is injected: tests pass one with a fake transport
        self.http = http

    def get(self, endpoint: str, key: str | int) -> dict:
        """Return the resource `endpoint/key` (e.g. "pokemon", 25), from cache if possible."""
        cache_file = self.cache_dir / endpoint / f"{key}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))

        response = self.http.get(f"{BASE_URL}{endpoint}/{key}/")
        response.raise_for_status()  # turns HTTP errors (404, 500...) into exceptions
        data = response.json()

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        return data

    def download(self, url: str, destination: Path) -> bool:
        """Download a media file unless it already exists. Return True if downloaded."""
        if destination.exists():
            return False
        response = self.http.get(url)
        response.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        return True
