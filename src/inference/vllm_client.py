"""Inference engine client for vLLM/TGI with continuous batching and token streaming."""
import logging
from typing import AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class VLLMClient:
    """Client for vLLM inference engine."""
    
    def __init__(self, base_url: str = "http://vllm-service:8000", timeout: float = 60.0):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.2,
        stream: bool = False,
        stop: Optional[List[str]] = None,
    ) -> Dict[str, any]:
        """
        Generate text using vLLM inference engine.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream tokens
            stop: Stop sequences
        
        Returns:
            Generated text and metadata
        """
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if stop:
            payload["stop"] = stop
        
        try:
            if stream:
                return await self._generate_stream(payload)
            else:
                response = await self.client.post(
                    f"{self.base_url}/v1/completions",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                return {
                    "text": result.get("choices", [{}])[0].get("text", ""),
                    "tokens": result.get("usage", {}),
                    "finish_reason": result.get("choices", [{}])[0].get("finish_reason"),
                }
        except httpx.HTTPError as e:
            logger.error(f"vLLM request failed: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in vLLM client: {e}")
            raise
    
    async def _generate_stream(self, payload: Dict) -> AsyncIterator[str]:
        """Stream tokens from vLLM."""
        async with self.client.stream(
            "POST",
            f"{self.base_url}/v1/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(data)
                        text = chunk.get("choices", [{}])[0].get("text", "")
                        if text:
                            yield text
                    except json.JSONDecodeError:
                        continue
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.2,
        stream: bool = False,
    ) -> Dict[str, any]:
        """
        Chat completion using vLLM (OpenAI-compatible API).
        
        Args:
            messages: List of message dicts with "role" and "content"
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream tokens
        
        Returns:
            Generated response and metadata
        """
        payload = {
            "model": "default",  # Model name configured in vLLM
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        
        try:
            if stream:
                return await self._chat_stream(payload)
            else:
                response = await self.client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                return {
                    "text": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
                    "tokens": result.get("usage", {}),
                    "finish_reason": result.get("choices", [{}])[0].get("finish_reason"),
                }
        except httpx.HTTPError as e:
            logger.error(f"vLLM chat request failed: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in vLLM chat: {e}")
            raise
    
    async def _chat_stream(self, payload: Dict) -> AsyncIterator[str]:
        """Stream chat tokens from vLLM."""
        async with self.client.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            yield text
                    except json.JSONDecodeError:
                        continue
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class TGIClient:
    """Client for Text Generation Inference (TGI) engine."""
    
    def __init__(self, base_url: str = "http://tgi-service:8000", timeout: float = 60.0):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def generate(
        self,
        inputs: str,
        parameters: Optional[Dict] = None,
    ) -> Dict[str, any]:
        """
        Generate text using TGI inference engine.
        
        Args:
            inputs: Input text
            parameters: Generation parameters (max_new_tokens, temperature, etc.)
        
        Returns:
            Generated text and metadata
        """
        payload = {
            "inputs": inputs,
            "parameters": parameters or {},
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/generate",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            return {
                "text": result.get("generated_text", ""),
                "tokens": result.get("details", {}).get("generated_tokens", 0),
            }
        except httpx.HTTPError as e:
            logger.error(f"TGI request failed: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in TGI client: {e}")
            raise
