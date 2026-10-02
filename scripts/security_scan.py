"""Scan built application images, retain full reports and fail on high/critical CVEs."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
reports = root / "artifacts" / "security"
reports.mkdir(parents=True, exist_ok=True)
cache = root.parent / ".tools" / "trivy-cache"
cache.mkdir(parents=True, exist_ok=True)
failed = False
for name, image in [("csharp", "banking-ledger-csharp:local"), ("audit-csharp", "banking-audit-csharp:local"), ("java", "banking-java:local")]:
    subprocess.run(["docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", cache.as_posix() + ":/root/.cache/trivy", "-v", reports.as_posix() + ":/reports",
        "aquasec/trivy:0.75.0", "image", "--timeout", "15m", "--java-db-repository", "ghcr.io/aquasecurity/trivy-java-db:1",
        "--scanners", "vuln", "--severity", "HIGH,CRITICAL", "--format", "json", "--output", f"/reports/trivy-{name}.json", image],
        cwd=root, check=True)
    result = json.loads((reports / f"trivy-{name}.json").read_text())
    findings = [v for target in result.get("Results", []) for v in target.get("Vulnerabilities", [])]
    for finding in findings:
        print(name, finding["VulnerabilityID"], finding["PkgName"], finding["InstalledVersion"], "->", finding.get("FixedVersion", "no fix"))
    print(f"{name}: {len(findings)} high/critical findings")
    failed |= bool(findings)
raise SystemExit(1 if failed else 0)
