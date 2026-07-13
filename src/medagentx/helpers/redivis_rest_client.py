"""
Redivis REST API helper.

This module avoids Redivis Python file-directory helpers such as:
    table.to_directory()
    table.file(...)

Those can fail on NRP with Arrow stream / timeout errors.

For raw file downloads, this helper uses the Redivis REST endpoint:
    GET /api/v1/rawFiles/{file_id}

Authentication:
    export REDIVIS_ACCESS_TOKEN="..."
or:
    export REDIVIS_API_TOKEN="..."
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests


REDIVIS_API_BASE_URL = "https://redivis.com/api/v1"


@dataclass
class RedivisDownloadResult:
    file_id: str
    output_path: str
    status: str
    bytes_written: int
    error: str = ""


class RedivisRestClient:
    def __init__(
        self,
        access_token,
        base_url=REDIVIS_API_BASE_URL,
        timeout=300,
        chunk_size=1024 * 1024,
        max_retries=3,
        retry_sleep=5,
    ):
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.retry_sleep = retry_sleep

    @classmethod
    def from_env(cls, **kwargs):
        access_token = (
            os.environ.get("REDIVIS_ACCESS_TOKEN")
            or os.environ.get("REDIVIS_API_TOKEN")
        )

        if not access_token:
            raise RuntimeError(
                "Missing Redivis token. Set REDIVIS_ACCESS_TOKEN or REDIVIS_API_TOKEN."
            )

        return cls(access_token=access_token, **kwargs)

    def headers(self, extra_headers=None):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def raw_file_url(self, file_id):
        return f"{self.base_url}/rawFiles/{file_id}"

    def get(self, path, **kwargs):
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = requests.get(
            url,
            headers=self.headers(),
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def download_raw_file(
        self,
        file_id,
        output_path,
        overwrite=False,
        resume=True,
    ):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists() and not overwrite:
            return RedivisDownloadResult(
                file_id=file_id,
                output_path=str(output_path),
                status="already_exists",
                bytes_written=output_path.stat().st_size,
            )

        mode = "wb"
        existing_bytes = 0
        extra_headers = {}

        if resume and output_path.exists() and not overwrite:
            existing_bytes = output_path.stat().st_size

            if existing_bytes > 0:
                mode = "ab"
                extra_headers["Range"] = f"bytes={existing_bytes}-"

        url = self.raw_file_url(file_id)
        last_error = ""

        for attempt in range(1, self.max_retries + 1):
            try:
                with requests.get(
                    url,
                    headers=self.headers(extra_headers),
                    timeout=self.timeout,
                    stream=True,
                ) as response:
                    if response.status_code == 416:
                        return RedivisDownloadResult(
                            file_id=file_id,
                            output_path=str(output_path),
                            status="already_exists",
                            bytes_written=output_path.stat().st_size,
                        )

                    response.raise_for_status()

                    with output_path.open(mode) as file_obj:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if chunk:
                                file_obj.write(chunk)

                return RedivisDownloadResult(
                    file_id=file_id,
                    output_path=str(output_path),
                    status="downloaded",
                    bytes_written=output_path.stat().st_size,
                )

            except Exception as error:
                last_error = f"{type(error).__name__}: {error}"

                if attempt < self.max_retries:
                    time.sleep(self.retry_sleep * attempt)

        return RedivisDownloadResult(
            file_id=file_id,
            output_path=str(output_path),
            status="failed",
            bytes_written=output_path.stat().st_size if output_path.exists() else 0,
            error=last_error,
        )