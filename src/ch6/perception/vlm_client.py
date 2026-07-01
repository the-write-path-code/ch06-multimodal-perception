# Section 6.3: Unified VLM Interface

import os
import json
import base64
import asyncio
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

        if config.use_local_vlm:
            return await self._call_local_vlm(prompt, img_bytes, response_schema)
        elif config.nvidia_api_key:
            return await self._call_nvidia(prompt, img_bytes, response_schema)
        else:
            return await self._call_gemini(prompt, img_bytes, response_schema)

    async def _call_nvidia(
        self,
        prompt: str,
        image_bytes: Optional[bytes],
        response_schema: Optional[Type[BaseModel]]
    ) -> Dict[str, Any]:
        """Calls NVIDIA NIM hosted VLM via OpenAI-compatible HTTP interface."""
        if not config.nvidia_api_key:
            raise ValueError("NVIDIA API key is missing.")

        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.nvidia_api_key}",
            "Content-Type": "application/json"
        }

        # Build prompt & base64 image content list
        prompt_str = prompt
        if response_schema:
            prompt_str += (
                "\n\nIMPORTANT: You must return ONLY a raw JSON object that strictly adheres to the requested schema. "
                "Do not include any conversational intro, outro, markdown block fences, explanations, or formatting. "
                "Provide only the raw JSON string starting with '{' and ending with '}'."
            )

        content_items = [{"type": "text", "text": prompt_str}]
        if image_bytes:
            b64_data = base64.b64encode(image_bytes).decode("utf-8")
            content_items.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_data}"}
            })

        payload = {
            "model": config.nvidia_vlm_model,
            "messages": [{"role": "user", "content": content_items}],
            "temperature": 0.2,
            "max_tokens": 1024
        }
        
        # Request JSON output structure if a schema is provided
        if response_schema:
            payload["response_format"] = {"type": "json_object"}

        # Implement exponential backoff for rate limiting (429 handling)
        max_retries = 3
        backoff_sec = 2.0
        
        async with httpx.AsyncClient() as client:
            for attempt in range(max_retries):
                try:
                    response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                    if response.status_code == 429:
                        logger.warning(
                            "NVIDIA VLM rate limited (429), retrying with backoff",
                            attempt=attempt+1,
                            backoff_seconds=backoff_sec
                        )
                        await asyncio.sleep(backoff_sec)
                        backoff_sec *= 2.0
                        continue
                    
                    response.raise_for_status()
                    result_json = response.json()
                    text_output = result_json["choices"][0]["message"]["content"].strip()
                    
                    if not text_output:
                        raise ValueError("NVIDIA VLM returned an empty response.")
                    
                    # Clean markdown code block wraps if returned
                    if text_output.startswith("```"):
                        lines = text_output.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        text_output = "\n".join(lines).strip()
                    
                    if response_schema:
                        # Extract substring between first '{' and last '}'
                        start = text_output.find("{")
                        end = text_output.rfind("}")
                        if start != -1 and end != -1 and end > start:
                            json_str = text_output[start:end+1]
                        else:
                            json_str = text_output

                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError as jde:
                            # Attempt basic key-value extraction from bullet points
                            # for resilience if JSON schema is completely ignored
                            fallback_dict = {}
                            for line in text_output.splitlines():
                                if ":" in line:
                                    parts = line.split(":", 1)
                                    key = parts[0].replace("*", "").replace("-", "").strip().lower()
                                    val = parts[1].strip()
                                    if key and val:
                                        fallback_dict[key] = val
                            
                            # Map keys to match common schemas (ImageAnalysisResult or AudioAnalysisSchema)
                            mapped = {}
                            if "title" in fallback_dict or "summary" in fallback_dict:
                                mapped = {
                                    "title": fallback_dict.get("title", "Analysis Result"),
                                    "summary": fallback_dict.get("summary", text_output),
                                    "entities": [v for k, v in fallback_dict.items() if k not in ("title", "summary", "confidence_score")],
                                    "confidence_score": 1.0
                                }
                            elif "summary" in fallback_dict or "entities" in fallback_dict:
                                mapped = {
                                    "summary": fallback_dict.get("summary", text_output),
                                    "entities": [e.strip() for e in fallback_dict.get("entities", "").split(",") if e.strip()] if fallback_dict.get("entities") else [],
                                    "action_items": [a.strip() for a in fallback_dict.get("action_items", "").split(",") if a.strip()] if fallback_dict.get("action_items") else [],
                                    "sentiment": fallback_dict.get("sentiment", "neutral"),
                                    "duration_seconds": float(fallback_dict.get("duration_seconds", 0.0)) if fallback_dict.get("duration_seconds") else 0.0
                                }
                            
                            if mapped:
                                logger.warning("Successfully constructed fallback dictionary from VLM text", mapped=mapped)
                                return mapped

                            logger.error("Failed to parse VLM response as JSON", text=text_output, clean_attempt=json_str, error=str(jde))
                            raise jde
                    return {"raw_text": text_output}
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < max_retries - 1:
                        await asyncio.sleep(backoff_sec)
                        backoff_sec *= 2.0
                        continue
                    logger.error("NVIDIA NIM VLM request failed with HTTP error", status=e.response.status_code, response=e.response.text)
                    raise e
                except Exception as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(backoff_sec)
                        backoff_sec *= 2.0
                        continue
                    logger.error("NVIDIA NIM VLM request failed", error=str(e))
                    raise e
            
            raise RuntimeError("NVIDIA NIM VLM call failed after maximum retries.")

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
