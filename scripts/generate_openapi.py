"""Generate the common, framework-independent OpenAPI 3.1 contract."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
uuid = {"type": "string", "format": "uuid"}
money = {"type": "integer", "minimum": 0, "maximum": 9_000_000_000_000}
currency = {"type": "string", "enum": ["USD", "EUR"]}
def obj(properties):
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}
def ref(name): return {"$ref": "#/components/schemas/" + name}
schemas = {
    "CreateAccount": obj({"id": uuid, "ownerId": {"type": "string", "minLength": 1}, "openingMinor": money, "currency": currency}),
    "Account": obj({"id": uuid, "ownerId": {"type": "string"}, "balanceMinor": money, "currency": currency, "version": {"type": "integer", "minimum": 1}}),
    "Transfer": obj({"sourceId": uuid, "destinationId": uuid, "amountMinor": {**money, "minimum": 1}, "currency": currency}),
    "Receipt": obj({"id": uuid, "sourceId": uuid, "destinationId": uuid, "amountMinor": {**money, "minimum": 1}, "currency": currency}),
    "AccountEvent": obj({"accountId": uuid, "version": {"type": "integer"}, "delta": {"type": "integer"}, "currency": currency}),
    "RiskSignal": obj({"amountMinor": money, "recentTransfers": {"type": "integer", "minimum": 0}, "sanctionsMatch": {"type": "boolean"}}),
    "RiskFinding": obj({"rule": {"type": "string"}, "blocked": {"type": "boolean"}, "reason": {"type": "string"}}),
    "SettlementRow": obj({"reference": {"type": "string"}, "minor": {"type": "integer"}}),
    "Reconciliation": obj({"internalRows": {"type": "array", "items": ref("SettlementRow")}, "providerRows": {"type": "array", "items": ref("SettlementRow")}}),
    "Discrepancy": obj({"reference": {"type": "string"}, "kind": {"type": "string"}}),
    "ProductRequest": obj({"id": uuid, "stock": {"type": "integer", "minimum": 0}}),
    "Product": obj({"id": uuid, "available": {"type": "integer", "minimum": 0}, "version": {"type": "integer", "minimum": 0}}),
    "Reservation": obj({"reservationId": uuid, "quantity": {"type": "integer", "minimum": 1}, "expectedVersion": {"type": "integer", "minimum": 0}}),
    "Onboarding": obj({"applicantReference": {"type": "string", "minLength": 1, "maxLength": 128}, "currency": currency}),
    "OnboardingResult": obj({"state": {"type": "string", "enum": ["Opened", "Rejected"]}, "accountId": {"type": ["string", "null"], "format": "uuid"}}),
}
paths = {}
def operation(path, method, name, request_schema, response_schema, status=200, role="reader", idempotency=False, array=False):
    parameters = [{"name": param, "in": "path", "required": True, "schema": uuid}
        for param in ("id", "reservationId") if "{" + param + "}" in path]
    if idempotency:
        parameters.append({"name": "Idempotency-Key", "in": "header", "required": True, "schema": uuid,
            "description": "Unique UUID per actor and operation; exact retries return the original result."})
    if method == "delete":
        parameters.append({"name": "expectedVersion", "in": "query", "required": True, "schema": {"type": "integer", "minimum": 0}})
    success = {"type": "array", "items": ref(response_schema)} if array else ref(response_schema)
    body = {"operationId": name, "description": "Required realm role: " + role,
        "parameters": parameters, "security": [{"bearerAuth": []}],
        "responses": {str(status): {"description": "Success", "content": {"application/json": {"schema": success}}},
            **{str(code): {"description": text} for code, text in [(400, "Invalid JSON contract"), (401, "Invalid or absent token"),
                (403, "Role or ownership denied"), (404, "Resource absent"), (409, "Conflict"), (422, "Business rule violation"), (500, "Infrastructure failure")]}}}
    if request_schema:
        body["requestBody"] = {"required": True, "content": {"application/json": {"schema": ref(request_schema)}}}
    paths.setdefault(path, {})[method] = body

operation("/api/accounts", "post", "openFixtureAccount", "CreateAccount", "Account", 201, "admin")
operation("/api/accounts/{id}", "get", "readAccount", None, "Account")
operation("/api/accounts/{id}/events", "get", "readHistory", None, "AccountEvent", array=True)
operation("/api/transfers", "post", "transfer", "Transfer", "Receipt", 201, "writer", idempotency=True)
operation("/api/risk/evaluate", "post", "evaluateRisk", "RiskSignal", "RiskFinding", role="writer", array=True)
operation("/api/reconciliation", "post", "reconcile", "Reconciliation", "Discrepancy", role="admin", array=True)
operation("/api/products", "post", "createProduct", "ProductRequest", "Product", 201, "admin")
operation("/api/products/{id}", "get", "readProduct", None, "Product")
operation("/api/products/{id}/reservations", "post", "reserve", "Reservation", "Product", 201, "writer")
operation("/api/products/{id}/reservations/{reservationId}", "delete", "cancelReservation", None, "Product", role="writer")
operation("/api/onboarding", "post", "onboard", "Onboarding", "OnboardingResult", 201, "writer", idempotency=True)
contract = {"openapi": "3.1.0", "info": {"title": "Banking Architecture Lab", "version": "1.0.0"},
    "servers": [{"url": "http://localhost:19081", "description": "C#"}, {"url": "http://localhost:19082", "description": "Java"}],
    "paths": paths, "components": {"schemas": schemas, "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}}}
(root / "contracts/openapi.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
print("Common API contract generated.")
