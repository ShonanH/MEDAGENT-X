from __future__ import annotations

from pathlib import Path

from medagentx.data.redivis_client import RedivisClient


class _Response:
    def __init__(self, *, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self.body = body
        self.headers: dict[str, str] = {}

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, *, chunk_size: int):
        del chunk_size
        yield self.body


def _client() -> RedivisClient:
    return RedivisClient(
        "test-token",
        max_retries=1,
        retry_sleep_seconds=0,
    )


def test_resume_appends_partial_content_for_206(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "image.dcm"
    partial = tmp_path / "image.dcm.part"
    partial.write_bytes(b"first-")
    seen_headers: list[dict[str, str]] = []

    def fake_get(*args: object, **kwargs: object) -> _Response:
        del args
        seen_headers.append(dict(kwargs["headers"]))
        return _Response(status_code=206, body=b"second")

    monkeypatch.setattr("medagentx.data.redivis_client.requests.get", fake_get)

    result = _client().download_raw_file("file-1", output)

    assert result.status == "downloaded"
    assert output.read_bytes() == b"first-second"
    assert not partial.exists()
    assert seen_headers[0]["Range"] == "bytes=6-"


def test_resume_restarts_partial_content_when_server_returns_200(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "image.dcm"
    partial = tmp_path / "image.dcm.part"
    partial.write_bytes(b"stale-partial")

    def fake_get(*args: object, **kwargs: object) -> _Response:
        del args, kwargs
        return _Response(status_code=200, body=b"complete-file")

    monkeypatch.setattr("medagentx.data.redivis_client.requests.get", fake_get)

    result = _client().download_raw_file("file-1", output)

    assert result.status == "downloaded"
    assert output.read_bytes() == b"complete-file"
    assert not partial.exists()
