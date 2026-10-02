"""Generate local Kubernetes manifests and an ignored Secret from .env.

The Docker Desktop host bridge connects to local Compose infrastructure.
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = dict(line.split("=", 1) for line in (root / ".env").read_text().splitlines() if "=" in line)
namespace = {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "banking-lab",
    "labels": {"pod-security.kubernetes.io/enforce": "restricted"}}}
common = {
    "KAFKA_BOOTSTRAP": "host.docker.internal:19094",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://host.docker.internal:19417",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
    "OTEL_METRICS_EXPORTER": "none", "OTEL_LOGS_EXPORTER": "none",
}
objects = [namespace]
for name, image, role, database, uid in [
    ("ledger-csharp", "banking-ledger-csharp:local", "ledger", "ledger_csharp", 1654),
    ("audit-csharp", "banking-audit-csharp:local", "audit", "audit_csharp", 1654),
    ("ledger-java", "banking-java:local", "ledger", "ledger_java", 100),
    ("audit-java", "banking-java:local", "audit", "audit_java", 100),
]:
    config = {**common, "KAFKA_TOPIC": "transfers." + ("csharp" if "csharp" in name else "java") + ".v1",
        "OTEL_SERVICE_NAME": name}
    if "csharp" in name:
        config.update(ASPNETCORE_ENVIRONMENT="Development", ASPNETCORE_URLS="http://+:8080")
        secret_ref = {"name": "DB_CONNECTION", "valueFrom": {"secretKeyRef": {"name": "banking-local", "key": database}}}
    else:
        config.update(DB_USER=database)
        config.update(OTEL_INSTRUMENTATION_COMMON_DEFAULT_ENABLED="false",
            OTEL_INSTRUMENTATION_TOMCAT_ENABLED="true",
            OTEL_INSTRUMENTATION_SPRING_WEBMVC_ENABLED="true",
            OTEL_INSTRUMENTATION_JDBC_ENABLED="true",
            OTEL_INSTRUMENTATION_KAFKA_ENABLED="true")
        config["LEDGER_JDBC_URL" if role == "ledger" else "AUDIT_JDBC_URL"] = f"jdbc:postgresql://host.docker.internal:15433/{database}"
        secret_ref = {"name": "DB_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "banking-local", "key": "password"}}}
    if role == "ledger":
        config.update(OUTBOX_MAX_AGE_SECONDS="60")
        config.update(OIDC_ISSUER="http://localhost:18180/realms/banking-lab",
            OIDC_JWKS="http://host.docker.internal:18180/realms/banking-lab/protocol/openid-connect/certs",
            OIDC_METADATA="http://host.docker.internal:18180/realms/banking-lab/.well-known/openid-configuration")
    else:
        config.update(KAFKA_GROUP=name + "-v1", BANK_MODE="audit", KAFKA_DLQ_TOPIC="transfers." + ("csharp" if "csharp" in name else "java") + ".dlq.v1")
    container = {
        "name": name, "image": image, "imagePullPolicy": "Never",
        "env": [{"name": key, "value": value} for key, value in sorted(config.items())] + [secret_ref],
        "resources": {"requests": {"cpu": "100m", "memory": "256Mi"},
            "limits": {"cpu": "1", "memory": "768Mi"}},
        "securityContext": {"allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]},
            "runAsNonRoot": True, "runAsUser": uid, "seccompProfile": {"type": "RuntimeDefault"}},
    }
    if role == "ledger":
        container["ports"] = [{"containerPort": 8080}]
        container["startupProbe"] = {"httpGet": {"path": "/health/live", "port": 8080}, "periodSeconds": 3, "timeoutSeconds": 3, "failureThreshold": 120}
        container["livenessProbe"] = {"httpGet": {"path": "/health/live", "port": 8080}, "periodSeconds": 10, "timeoutSeconds": 3, "failureThreshold": 6}
        container["readinessProbe"] = {"httpGet": {"path": "/health/ready", "port": 8080}, "periodSeconds": 5, "timeoutSeconds": 3}
        objects.append({"apiVersion": "v1", "kind": "Service", "metadata": {"name": name, "namespace": "banking-lab"},
            "spec": {"selector": {"app": name}, "ports": [{"port": 8080, "targetPort": 8080}]}})
    objects.append({"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": name, "namespace": "banking-lab"},
        "spec": {"replicas": 1, "revisionHistoryLimit": 3, "selector": {"matchLabels": {"app": name}},
            "template": {"metadata": {"labels": {"app": name}}, "spec": {
                "automountServiceAccountToken": False, "terminationGracePeriodSeconds": 30, "containers": [container]}}}})
manifests = {"apiVersion": "v1", "kind": "List", "items": objects}
(root / "k8s" / "local.json").write_text(json.dumps(manifests, indent=2) + "\n", encoding="utf-8")
secret = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "banking-local", "namespace": "banking-lab"},
    "type": "Opaque", "stringData": {"password": env["DB_PASSWORD"],
        **{db: f"Host=host.docker.internal;Port=15433;Database={db};Username={db};Password={env['DB_PASSWORD']}"
            for db in ("ledger_csharp", "audit_csharp")}}}
destination = root / "artifacts" / "k8s"
destination.mkdir(parents=True, exist_ok=True)
(destination / "secret.json").write_text(json.dumps(secret), encoding="utf-8")
print("Kubernetes manifests generated; Secret remains in artifacts/k8s.")
