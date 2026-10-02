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
schema = json.loads((root / "contracts/transfer-completed.v1.schema.json").read_text())
assert set(schema["required"]) == set(schema["properties"])
assert schema["additionalProperties"] is False
print("Architecture boundaries and v1 event shape verified.")
