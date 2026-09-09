"""Unified REST client for Redivis SQL queries and raw file downloads."""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.constants import (
    REDIVIS_API_BASE_URL,
    REDIVIS_API_TOKEN_ENV,
)


@dataclass(frozen=True)
class RedivisDownloadResult:
    """Result of one rawFiles download attempt."""

    file_id: str
    output_path: str
    status: str
    bytes_written: int
    error: str = ""


class RedivisClient:
    """REST-only Redivis client (queries + rawFiles)."""

    def __init__(
        self,
        api_token: str,
        *,
        base_url: str = REDIVIS_API_BASE_URL,
        timeout_seconds: int = 300,
        query_timeout_ms: int = 60000,
        max_retries: int = 3,
        retry_sleep_seconds: float = 5.0,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        if not isinstance(api_token, str) or not api_token.strip():
            raise ValueError("api_token must be a non-empty string")

        self.api_token = api_token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.query_timeout_ms = query_timeout_ms
        self.max_retries = max_retries
        self.retry_sleep_seconds = retry_sleep_seconds
        self.chunk_size = chunk_size

    @classmethod
    def from_env(cls, **kwargs: Any) -> "RedivisClient":
        """Create a client using REDIVIS_API_TOKEN only."""
        token = os.environ.get(REDIVIS_API_TOKEN_ENV)
        if not token or not token.strip():
            raise RuntimeError(
                f"Missing Redivis token. Set {REDIVIS_API_TOKEN_ENV}."
            )
        return cls(api_token=token, **kwargs)

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _get_query_id(self, payload: dict[str, Any]) -> str:
        for key in ("id", "queryId", "referenceId"):
            value = payload.get(key)
            if value:
                return str(value)

        uri = str(payload.get("uri", ""))
        match = re.search(r"/queries/([^/]+)", uri)
        if match:
            return match.group(1)

        raise RuntimeError(f"Could not determine query id from: {payload}")

    def _wait_for_query(
        self,
        query_id: str,
        *,
        timeout_seconds: int = 600,
    ) -> None:
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            response = requests.get(
                f"{self.base_url}/queries/{query_id}",
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Redivis query GET failed HTTP {response.status_code}: "
                    f"{response.text[:2000]}"
                )

            payload = response.json()
            status = str(payload.get("status", "")).lower()

            if status in {"completed", "succeeded", "success"}:
                return
            if status in {"failed", "error", "cancelled", "canceled"}:
                raise RuntimeError(f"Redivis query failed: {payload}")

            time.sleep(self.retry_sleep_seconds)

        raise TimeoutError(f"Timed out waiting for Redivis query {query_id}")

    def run_sql_query(
        self,
        query: str,
        *,
        max_results: int = 100000,
    ) -> pd.DataFrame:
        """Run a SQL query via REST and return rows as a DataFrame."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if max_results <= 0:
            raise ValueError("max_results must be > 0")

        post = requests.post(
            f"{self.base_url}/queries",
            headers=self._headers({"Content-Type": "application/json"}),
            json={"query": query, "timeoutMs": self.query_timeout_ms},
            timeout=self.timeout_seconds,
        )
        if post.status_code >= 400:
            raise RuntimeError(
                f"Redivis query POST failed HTTP {post.status_code}: "
                f"{post.text[:2000]}"
            )

        payload = post.json()
        query_id = self._get_query_id(payload)
        status = str(payload.get("status", "")).lower()
        if status not in {"completed", "succeeded", "success"}:
            self._wait_for_query(query_id)

        rows = requests.get(
            f"{self.base_url}/queries/{query_id}/rows",
            headers=self._headers(),
            params={"format": "csv", "maxResults": max_results},
            timeout=self.timeout_seconds,
        )
        if rows.status_code >= 400:
            raise RuntimeError(
                f"Redivis rows download failed HTTP {rows.status_code}: "
                f"{rows.text[:2000]}"
            )

        text = rows.text
        if not text.strip():
            return pd.DataFrame()
        try:
            return pd.read_csv(StringIO(text), dtype=str)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    def download_raw_file(
        self,
        file_id: str,
        output_path: str | Path,
        *,
        overwrite: bool = False,
        resume: bool = True,
    ) -> RedivisDownloadResult:
        """Download one file via GET /rawFiles/{file_id}."""
        if not isinstance(file_id, str) or not file_id.strip():
            raise ValueError("file_id must be a non-empty string")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        partial = output.with_name(f"{output.name}.part")

        if output.exists() and not overwrite:
            size = output.stat().st_size
            if size > 0:
                return RedivisDownloadResult(
                    file_id=file_id,
                    output_path=str(output),
                    status="already_exists",
                    bytes_written=size,
                )

        if overwrite:
            output.unlink(missing_ok=True)
            partial.unlink(missing_ok=True)
        elif not resume:
            partial.unlink(missing_ok=True)

        url = f"{self.base_url}/rawFiles/{file_id.strip()}"
        last_error = ""

        for _ in range(self.max_retries):
            try:
                partial_size = partial.stat().st_size if partial.exists() else 0
                extra_headers = (
                    {"Range": f"bytes={partial_size}-"}
                    if resume and partial_size > 0
                    else {}
                )
                with requests.get(
                    url,
                    headers=self._headers(extra_headers),
                    timeout=self.timeout_seconds,
                    stream=True,
                ) as response:
                    if response.status_code == 416:
                        match = re.search(
                            r"\*/(\d+)", response.headers.get("Content-Range", "")
                        )
                        expected_size = int(match.group(1)) if match else None
                        if (
                            expected_size is not None
                            and partial_size == expected_size
                        ):
                            os.replace(partial, output)
                            return RedivisDownloadResult(
                                file_id=file_id,
                                output_path=str(output),
                                status="downloaded",
                                bytes_written=output.stat().st_size,
                            )
                        partial.unlink(missing_ok=True)
                        raise RuntimeError(
                            "Redivis rejected the resume offset; partial file reset"
                        )
                    response.raise_for_status()

                    # A compliant range response is 206. If the server returns
                    # 200, restart the partial file instead of appending a full
                    # response to it.
                    mode = (
                        "ab"
                        if partial_size > 0 and response.status_code == 206
                        else "wb"
                    )
                    with partial.open(mode) as handle:
                        for chunk in response.iter_content(
                            chunk_size=self.chunk_size
                        ):
                            if chunk:
                                handle.write(chunk)

                os.replace(partial, output)

                return RedivisDownloadResult(
                    file_id=file_id,
                    output_path=str(output),
                    status="downloaded",
                    bytes_written=output.stat().st_size,
                )
            except Exception as exc:  # noqa: BLE001 - retry then surface
                last_error = str(exc)
                time.sleep(self.retry_sleep_seconds)

        return RedivisDownloadResult(
            file_id=file_id,
            output_path=str(output),
            status="failed",
            bytes_written=(
                partial.stat().st_size
                if partial.exists()
                else (output.stat().st_size if output.exists() else 0)
            ),
            error=last_error,
        )
