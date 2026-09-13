import json
from typing import Any, Protocol

from jsonschema import validate
from openai import AsyncOpenAI

from app.config import Settings


class LLMProvider(Protocol):
    async def extract(self, content: str, schema: dict[str, Any]) -> dict[str, Any]: ...


def compact_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if "type" in schema and "properties" in schema:
        return schema
    properties: dict[str, Any] = {}
    for name, kind in schema.items():
        properties[name] = {
            "type": kind
            if kind in {"string", "number", "integer", "boolean", "array", "object"}
            else "string"
        }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("LLM is disabled")
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(), base_url=settings.openai_base_url
        )
        self.model = settings.openai_model

    async def extract(self, content: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.responses.create(
            model=self.model,
            input=[
                {"role": "user", "content": f"Extract fields from this page.\n\n{content[:50000]}"}
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "extraction",
                    "schema": compact_schema(schema),
                    "strict": True,
                }
            },
            store=False,
        )
        data = json.loads(response.output_text)
        validate(instance=data, schema=compact_schema(schema))
        return data
