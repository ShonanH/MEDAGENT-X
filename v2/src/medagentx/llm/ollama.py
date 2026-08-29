"""Shared Ollama HTTP client for MEDAGENT-X LLM agents."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_OLLAMA_MODEL = "gpt-oss:120b"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 300


class OllamaClientError(RuntimeError):
    """Raised when the Ollama API call fails or returns invalid content."""


@dataclass(frozen=True)
class OllamaConfig:
   """Runtime configuration for Ollama client."""

   model: str = DEFAULT_OLLAMA_MODEL
   base_url: str = DEFAULT_OLLAMA_BASE_URL
   temperature: float = 0.0
   timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

   @classmethod
   def from_env(cls) -> "OllamaConfig":
       """Build config from MEDAGENT-X environment variables."""

       return cls(
           model=os.getenv("MEDAGENTX_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
           base_url=os.getenv("MEDAGENTX_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
           temperature=float(os.getenv("MEDAGENTX_OLLAMA_TEMPERATURE", "0")),
           timeout_seconds=int(os.getenv("MEDAGENTX_OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
       )

class OllamaClient:
   """Small direct HTTP client for Ollama chat completions."""

   def __init__(self, config: OllamaConfig | None = None) -> None:
      self.config = config or OllamaConfig.from_env()

   def chat_json(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
      """Call Ollama chat and parse the response content as JSON.
      
      Args: 
         system_prompt: System instructions for the model.
         user_prompt: Task payload.
         schema: Optional JSON schema passed to Ollama.

      Returns:
         Parsed JSON object from the model response
      
      Raises:
         OllamaClientError if the API fails or the model returns invalid JSON.

      """

      payload: dict[str, Any] = {
         "model": self.config.model,
         "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
         ],
         "stream": False,
         "options":{
            "temperature": self.config.temperature,
         },
      }

      if schema is not None:
         payload["format"] = schema
      else:
         payload["format"] = "json"

      response = self._post_json("/api/chat", payload)
      message = response.get("message")
      if not isinstance(message, dict):
         raise OllamaClientError("Response is missing message object")

      content = message.get("content")
      if not isinstance(content, str) or not content.strip():
         raise OllamaClientError("Response is missing message content")

      try:
         parsed = json.loads(content)
      except json.JSONDecodeError as exc:
         raise OllamaClientError("Response is not a valid JSON object") from exc

      if not isinstance(parsed, dict):
         raise OllamaClientError("Response must be an object")

      return parsed

   def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
      url = self.config.base_url.rstrip("/") + path
      body = json.dumps(payload).encode("utf-8")
      request = Request(
         url, data=body, headers={"Content-Type": "application/json"}, method="POST",
      )

      try:
         with urlopen(request, timeout=self.config.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
      except HTTPError as exc:
         detail = exc.read().decode("utf-8", errors="replace")
         raise OllamaClientError(f"Ollama HTTP error {exc.code}: {detail}") from exc
      except URLError as exc:
         raise OllamaClientError(f"Ollama connection error: {exc}") from exc
      except TimeoutError as exc:
         raise OllamaClientError(f"Ollama request timed out") from exc


      try:
         parsed = json.loads(raw)
      except json.JSONDecodeError as exc:
         raise OllamaClientError("Ollama API returned invalid JSON") from exc

      if not isinstance(parsed, dict):
         raise OllamaClientError("Response must be an object")

      if "error" in parsed:
         raise OllamaClientError(f"Ollama API error: {parsed['error']}")

      return parsed


