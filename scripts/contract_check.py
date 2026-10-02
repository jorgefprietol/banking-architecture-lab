"""Validate the JSON Schema subset used by our shared OpenAPI contract."""
import json
from pathlib import Path
import re
import uuid

root = Path(__file__).resolve().parents[1]
contract = json.loads((root / "contracts/openapi.json").read_text())

def validate(value, schema):
    if "$ref" in schema:
        schema = contract["components"]["schemas"][schema["$ref"].split("/")[-1]]
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected]
    actual = "null" if value is None else "boolean" if type(value) is bool else "integer" if type(value) is int else \
        "number" if type(value) is float else "string" if isinstance(value, str) else "array" if isinstance(value, list) else "object"
    assert actual in types, (actual, expected, value)
    if value is None: return
    if "enum" in schema: assert value in schema["enum"], value
    if "const" in schema: assert value == schema["const"], value
    if schema.get("format") == "uuid": uuid.UUID(value)
    if actual in ("integer", "number"):
        if "minimum" in schema: assert value >= schema["minimum"], value
        if "maximum" in schema: assert value <= schema["maximum"], value
    if actual == "array":
        for item in value: validate(item, schema["items"])
    if actual == "object":
        assert set(schema.get("required", [])) <= value.keys(), value
        if schema.get("additionalProperties") is False: assert value.keys() <= schema["properties"].keys(), value
        for key, item in value.items():
            if key in schema.get("properties", {}): validate(item, schema["properties"][key])

def validate_response(method, path, status, value):
    if not 200 <= status < 300: return
    path = path.split("?")[0]
    for template, operations in contract["paths"].items():
        pattern = re.sub(r"\{[^}]+\}", "[^/]+", template)
        if re.fullmatch(pattern, path) and method.lower() in operations:
            response = operations[method.lower()]["responses"][str(status)]
            validate(value, response["content"]["application/json"]["schema"])
            return
