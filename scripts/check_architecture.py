"""Enforce source boundaries and contract shape in both implementations."""
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
for language, directories in {
    "csharp": ["csharp/Banking.Domain", "csharp/Banking.Application"],
    "java": ["java/src/main/java/dev/portfolio/banking/domain", "java/src/main/java/dev/portfolio/banking/application"],
}.items():
    for directory in directories:
        suffix = ".cs" if language == "csharp" else ".java"
        for source in (root / directory).glob("*" + suffix):
            imports = "\n".join(line for line in source.read_text().splitlines() if line.startswith(("using ", "import ")))
            assert not re.search(r"Npgsql|Confluent|Microsoft\.AspNetCore|org\.springframework|org\.apache\.kafka|\.Infrastructure|\.infrastructure", imports), source
            if "Domain" in directory or directory.endswith("/domain"):
                assert not re.search(r"\.Application|\.application", imports), source
for contract in ("transfer-completed.v1.schema.json", "audit-event-rejected.v1.schema.json"):
    schema = json.loads((root / "contracts" / contract).read_text())
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
java_image_lines = re.findall(r"eclipse-temurin[-:]([0-9]+)", (root / "java/Dockerfile").read_text())
assert len(java_image_lines) == 2 and set(java_image_lines) == {"25"}, "Build and runtime images must use the tested Java 25 LTS line"
print("Architecture boundaries, v1 event shape and Java LTS image policy verified.")
release = (root / ".github/workflows/release.yml").read_text()
assert "build-push-action" not in release and "setup-buildx-action" not in release and not re.search(r"docker (?:compose )?build", release), "Release must promote the tested bundle without rebuilding"
assert "image_bundle.py promote" in release and "actions/download-artifact@" in release
print("Release promotes the tested image bundle without rebuilding.")
