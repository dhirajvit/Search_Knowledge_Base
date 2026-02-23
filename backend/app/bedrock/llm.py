import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import boto3
from langfuse import observe
from langfuse import get_client

bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("DEFAULT_AWS_REGION", "ap-southeast-2"),
)

# Pricing per 1M tokens — update as AWS pricing changes
BEDROCK_PRICING = {
    "amazon.nova-lite-v1:0": {"input": 0.06, "output": 0.24},
    "amazon.nova-micro-v1:0": {"input": 0.035, "output": 0.14},
    "amazon.nova-pro-v1:0": {"input": 0.80, "output": 3.20},
    "amazon.titan-embed-text-v2:0": {"input": 0.02, "output": 0.0},
}


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    duration_ms: float
    cost: float


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = BEDROCK_PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]


@observe(as_type="generation")
def call_bedrock(
    prompt: str,
    model: str,
    system: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    metadata: Optional[Dict[str, Any]] = None,
) -> LLMResponse:
    """Call a Bedrock converse model with full Langfuse observability."""
    start = time.time()

    messages = [{"role": "user", "content": [{"text": prompt}]}]
    kwargs: Dict[str, Any] = {
        "modelId": model,
        "messages": messages,
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature, "topP": 0.9},
    }
    if system:
        kwargs["system"] = [{"text": system}]

    response = bedrock_client.converse(**kwargs)

    duration_ms = (time.time() - start) * 1000
    usage = response.get("usage", {})
    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    cost = calculate_cost(model, input_tokens, output_tokens)

    get_client().update_current_generation(
        model=model,
        usage_details={
            "input": input_tokens,
            "output": output_tokens,
            "total": usage.get("totalTokens", 0),
        },
        metadata={
            **(metadata or {}),
            "duration_ms": duration_ms,
            "cost": cost,
            "stop_reason": response.get("stopReason"),
        },
    )

    return LLMResponse(
        content=response["output"]["message"]["content"][0]["text"],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        duration_ms=duration_ms,
        cost=cost,
    )
