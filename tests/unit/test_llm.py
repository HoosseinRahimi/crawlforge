from app.llm.provider import compact_schema


def test_compact_schema_becomes_strict_object_schema() -> None:
    schema = compact_schema({"name": "string", "price": "number"})
    assert schema["type"] == "object"
    assert schema["required"] == ["name", "price"]
    assert schema["additionalProperties"] is False


def test_json_schema_passes_through() -> None:
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    assert compact_schema(schema) is schema
