"""HTTP client used by Streamlit to talk to the FastAPI backend."""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_TIMEOUT = 20


class ApiError(Exception):
    def __init__(self, message: str, *, status_code: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BackendClient:
    def __init__(self, base_url: str, token: str = "") -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.token = token or ""
        self.session = requests.Session()

    def set_token(self, token: str) -> None:
        self.token = token or ""

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.base_url}{path if path.startswith('/') else '/' + path}"

    def _detail(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            text = (response.text or "").strip()
            return text or f"HTTP {response.status_code}"
        if isinstance(payload, dict):
            detail = payload.get("detail") or payload.get("message") or ""
            if isinstance(detail, list) and detail:
                first = detail[0]
                if isinstance(first, dict):
                    return str(first.get("msg") or first)
                return str(first)
            if detail:
                return str(detail)
        return f"HTTP {response.status_code}"

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        data: Any = None,
        files: Any = None,
        params: dict[str, Any] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        try:
            response = self.session.request(
                method,
                self._url(path),
                headers=self._headers(),
                json=json,
                data=data,
                files=files,
                params=params,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise ApiError(str(exc) or "API injoignable") from exc
        if response.status_code >= 400:
            raise ApiError(self._detail(response), status_code=response.status_code)
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        return self.request("PATCH", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)

    def health(self) -> bool:
        try:
            payload = self.get("/health", timeout=3)
        except ApiError:
            return False
        return isinstance(payload, dict) and payload.get("status") == "ok"
