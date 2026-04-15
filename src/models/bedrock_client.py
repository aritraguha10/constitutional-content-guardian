"""
AWS Bedrock Client Wrapper for Claude Models

This module provides a reusable client for interacting with Claude models
via AWS Bedrock, with proper error handling, retry logic, and token tracking.
"""

import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError
from loguru import logger


@dataclass
class BedrockResponse:
    """Structured response from Bedrock API"""
    content: str
    model_id: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    latency_ms: float


class BedrockClient:
    """
    AWS Bedrock client wrapper for Claude models with retry logic and error handling.

    Usage:
        client = BedrockClient(region="us-east-1")
        response = client.invoke(
            prompt="What is HIPAA?",
            system_prompt="You are a compliance expert."
        )
        print(response.content)
    """

    def __init__(
        self,
        region: str = "us-east-1",
        model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize Bedrock client.

        Args:
            region: AWS region for Bedrock
            model_id: Claude model ID (e.g., anthropic.claude-opus-4-6-v1)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)
            max_retries: Maximum number of retry attempts on failure
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.region = region
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Initialize Bedrock runtime client
        try:
            self.client = boto3.client(
                service_name="bedrock-runtime",
                region_name=region
            )
            logger.info(f"✓ Initialized Bedrock client for region: {region}, model: {model_id}")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Bedrock client: {e}")
            raise

    def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> BedrockResponse:
        """
        Invoke Claude model with retry logic.

        Args:
            prompt: User prompt/question
            system_prompt: Optional system prompt for context
            max_tokens: Override default max_tokens
            temperature: Override default temperature
            stop_sequences: Optional stop sequences

        Returns:
            BedrockResponse with content and metadata

        Raises:
            Exception: After max retries exhausted
        """
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        # Build request body
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        if system_prompt:
            request_body["system"] = system_prompt

        if stop_sequences:
            request_body["stop_sequences"] = stop_sequences

        # Retry loop with exponential backoff
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )

                latency_ms = (time.time() - start_time) * 1000

                # Parse response
                response_body = json.loads(response["body"].read())

                # Extract content
                content = ""
                if "content" in response_body and len(response_body["content"]) > 0:
                    content = response_body["content"][0]["text"]

                # Build structured response
                bedrock_response = BedrockResponse(
                    content=content,
                    model_id=self.model_id,
                    input_tokens=response_body.get("usage", {}).get("input_tokens", 0),
                    output_tokens=response_body.get("usage", {}).get("output_tokens", 0),
                    stop_reason=response_body.get("stop_reason", "unknown"),
                    latency_ms=latency_ms
                )

                logger.debug(
                    f"✓ Model invoked successfully | "
                    f"Input: {bedrock_response.input_tokens} tokens | "
                    f"Output: {bedrock_response.output_tokens} tokens | "
                    f"Latency: {latency_ms:.0f}ms"
                )

                return bedrock_response

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_message = e.response.get("Error", {}).get("Message", str(e))

                logger.warning(
                    f"⚠ Bedrock API error (attempt {attempt + 1}/{self.max_retries}): "
                    f"{error_code} - {error_message}"
                )

                # Check if retryable
                if error_code in ["ThrottlingException", "ServiceUnavailableException"]:
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.info(f"⏳ Retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        continue

                # Non-retryable error or max retries exceeded
                logger.error(f"✗ Bedrock invocation failed: {error_message}")
                raise

            except Exception as e:
                logger.error(f"✗ Unexpected error during Bedrock invocation: {e}")
                raise

        raise Exception(f"Max retries ({self.max_retries}) exhausted")

    def invoke_with_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> BedrockResponse:
        """
        Invoke Claude with multi-turn conversation.

        Args:
            messages: List of message dicts with 'role' and 'content'
                     Example: [{"role": "user", "content": "Hello"}]
            system_prompt: Optional system prompt
            max_tokens: Override default max_tokens
            temperature: Override default temperature

        Returns:
            BedrockResponse with content and metadata
        """
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }

        if system_prompt:
            request_body["system"] = system_prompt

        try:
            start_time = time.time()

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            latency_ms = (time.time() - start_time) * 1000
            response_body = json.loads(response["body"].read())

            content = ""
            if "content" in response_body and len(response_body["content"]) > 0:
                content = response_body["content"][0]["text"]

            return BedrockResponse(
                content=content,
                model_id=self.model_id,
                input_tokens=response_body.get("usage", {}).get("input_tokens", 0),
                output_tokens=response_body.get("usage", {}).get("output_tokens", 0),
                stop_reason=response_body.get("stop_reason", "unknown"),
                latency_ms=latency_ms
            )

        except Exception as e:
            logger.error(f"✗ Bedrock invocation with messages failed: {e}")
            raise

    def test_connection(self) -> bool:
        """
        Test Bedrock connection with a simple query.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self.invoke(
                prompt="Respond with 'OK' if you can read this.",
                max_tokens=10
            )
            logger.info(f"✓ Bedrock connection test successful: {response.content}")
            return True
        except Exception as e:
            logger.error(f"✗ Bedrock connection test failed: {e}")
            return False


# Convenience function for quick invocations
def quick_invoke(
    prompt: str,
    system_prompt: Optional[str] = None,
    region: str = "us-east-1",
    model_id: str = "anthropic.claude-opus-4-6-v1"
) -> str:
    """
    Quick one-off invocation without creating a persistent client.

    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        region: AWS region
        model_id: Claude model ID

    Returns:
        Response content as string
    """
    client = BedrockClient(region=region, model_id=model_id)
    response = client.invoke(prompt=prompt, system_prompt=system_prompt)
    return response.content


if __name__ == "__main__":
    # Test the client
    from loguru import logger
    import sys

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    print("Testing Bedrock Client...\n")

    try:
        # Initialize client (using cross-region inference profile)
        client = BedrockClient(
            region="us-east-1",
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )

        # Test connection
        if client.test_connection():
            print("[OK] Connection test passed!\n")

            # Test actual invocation
            print("Testing compliance query...")
            response = client.invoke(
                prompt="What are the key principles of HIPAA compliance?",
                system_prompt="You are a healthcare compliance expert.",
                max_tokens=500
            )

            print(f"\nResponse:\n{response.content}\n")
            print(f"Tokens: {response.input_tokens} in, {response.output_tokens} out")
            print(f"Latency: {response.latency_ms:.0f}ms")
            print("\n[SUCCESS] All tests passed!")
        else:
            print("[FAIL] Connection test failed")

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
