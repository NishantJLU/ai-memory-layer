import httpx
from typing import List, Dict, Any


class MemoryClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        """
        Initialize the AI Memory Layer client.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        self.headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key

    def ingest(self, repo_path: str, project_id: str = "default", max_commits: int = 10) -> Dict[str, Any]:
        """
        Trigger an asynchronous ingestion of a local git repository.
        """
        response = httpx.post(
            f"{self.base_url}/ingest",
            json={
                "repo_path": repo_path,
                "project_id": project_id,
                "max_commits": max_commits
            },
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def recall(self, query: str, project_id: str = "default", limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recall semantically relevant past decisions.
        """
        response = httpx.post(
            f"{self.base_url}/recall",
            json={
                "query": query,
                "project_id": project_id,
                "limit": limit
            },
            headers=self.headers
        )
        response.raise_for_status()
        return response.json().get("results", [])

    def health(self) -> Dict[str, Any]:
        """
        Check if the memory layer is running.
        """
        response = httpx.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
