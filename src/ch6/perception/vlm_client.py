# Section 6.3: Unified VLM Interface

import os
import json
import base64
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel
from google import genai
from google.genai import types
import httpx
from ch6.config import config
from ch6.logging import logger

class VLMClient:
    """Unified client routing requests to Gemini (Cloud) or Ollama (Local VLM)."""

    def __init__(self) -> None:
        self.gemini_client: Optional[genai.Client] = None
        if config.gemini_api_key:
            self.gemini_client = genai.Client(api_key=config.gemini_api_key)
        elif not config.use_local_vlm:
            logger.warning("No GEMINI_API_KEY provided. VLM calls will fail or fallback to local VLM if enabled.")

    async def analyze_image(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        response_schema: Optional[Type[BaseModel]] = None
    ) -> Dict[str, Any]:
        """Analyzes an image (file path or raw bytes) and returns structured JSON output.

        Attempts to call Google Gemini (default) or falls back to Ollama when USE_LOCAL_VLM=True.
        """
        # Read image to bytes if path is provided
        img_bytes = None
        if image_bytes:
            img_bytes = image_bytes
        elif image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                img_bytes = f.read()

        if config.use_local_vlm or not self.gemini_client:
            return await self._call_local_vlm(prompt, img_bytes, response_schema)
        else:
            return await self._call_gemini(prompt, img_bytes, response_schema)

    async def _call_gemini(
        self,
        prompt: str,
        image_bytes: Optional[bytes],
        response_schema: Optional[Type[BaseModel]]
    ) -> Dict[str, Any]:
        """Calls Google Gemini Cloud VLM using the google-genai SDK."""
        if not self.gemini_client:
            raise ValueError("Gemini client is not initialized (missing API key).")

        contents: list[Any] = [prompt]
        if image_bytes:
            contents.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/png"
                )
            )

        # Build schema parameters if pydantic model provided
        config_params = {}
        if response_schema:
            config_params["response_mime_type"] = "application/json"
            config_params["response_schema"] = response_schema

        try:
            # Running genai client call in a thread pool as it is synchronous in the SDK
            loop = asyncio.get_running_loop()
        except RuntimeError:
            import asyncio
            loop = asyncio.get_event_loop()

        def _sync_call():
            # Use gemini-2.5-flash as the standard fast multimodal model
            return self.gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(**config_params) if config_params else None
            )

        try:
            response = await loop.run_in_executor(None, _sync_call)
            text_output = response.text
            if not text_output:
                raise ValueError("VLM returned empty response")

            if response_schema:
                return json.loads(text_output)
            return {"raw_text": text_output}
        except Exception as e:
            logger.error("Gemini VLM API call failed", error=str(e))
            raise e

    async def _call_local_vlm(
        self,
        prompt: str,
        image_bytes: Optional[bytes],
        response_schema: Optional[Type[BaseModel]]
    ) -> Dict[str, Any]:
        """Calls local Ollama VLM (e.g. LLaVA or similar multimodal models)."""
        # Format image for Ollama (requires base64 string or file path)
        images = []
        if image_bytes:
            images.append(base64.b64encode(image_bytes).decode("utf-8"))

        payload = {
            "model": config.local_vlm_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": images if images else None
                }
            ],
            "stream": False
        }

        # Ollama doesn't have strict schema enforcement out-of-the-box in all versions,
        # so we append formatting instructions to the prompt if response_schema is provided.
        if response_schema:
            schema_description = json.dumps(response_schema.model_json_schema(), indent=2)
            payload["messages"][0]["content"] += (
                f"\n\nYou MUST reply strictly in JSON matching this schema:\n{schema_description}"
            )
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{config.ollama_host}/api/chat"
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama returned HTTP {response.status_code}: {response.text}")
                
                resp_json = response.json()
                message_content = resp_json["message"]["content"]
                
                if response_schema:
                    return json.loads(message_content)
                return {"raw_text": message_content}
        except Exception as e:
            logger.error("Local Ollama VLM call failed", error=str(e))
            raise e
