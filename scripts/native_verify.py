"""Run compiled applications against local Compose infrastructure without Docker builds.

Windows: --dotnet D:/Cursos/.tools/dotnet/dotnet.exe --java C:/path/to/java.exe
Build the solution and run mvn verify first. Only subprocesses started here are stopped.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from integration_test import ROOT, ENV

def verify(args):
    if not args.reuse_infrastructure:
        subprocess.run(["docker", "compose", "up", "-d", "postgres", "kafka-init", "keycloak", "jaeger"], cwd=ROOT, check=True)
        initialized = subprocess.run(["docker", "wait", "banking-lab-kafka-init-1"], cwd=ROOT, check=True, capture_output=True, text=True, timeout=600)
        if initialized.stdout.strip() != "0": raise RuntimeError("Kafka topic initialization failed")
    subprocess.run([sys.executable, "scripts/migrate.py"], cwd=ROOT, check=True)
    directory = ROOT/"artifacts"/"native"; directory.mkdir(parents=True, exist_ok=True)
    processes = []; streams = []
    try:
        for language in ("csharp", "java"):
            for mode in ("ledger", "audit"):
                name = mode+"-"+language; database = mode+"_"+language
                environment = {**os.environ, "KAFKA_BOOTSTRAP": "localhost:19092", "KAFKA_TOPIC": "transfers."+language+".v1",
                    "KAFKA_DLQ_TOPIC": "transfers."+language+".dlq.v1", "KAFKA_GROUP": "audit-"+language+"-v1", "OUTBOX_MAX_AGE_SECONDS": "60",
                    "DB_CONNECTION": "Host=localhost;Port=15433;Database="+database+";Username="+database+";Password="+ENV["DB_PASSWORD"],
                    "DB_USER": database, "DB_PASSWORD": ENV["DB_PASSWORD"], "BANK_MODE": mode,
                    "LEDGER_JDBC_URL": "jdbc:postgresql://localhost:15433/"+database, "AUDIT_JDBC_URL": "jdbc:postgresql://localhost:15433/"+database,
                    "OIDC_ISSUER": "http://localhost:18180/realms/banking-lab", "OIDC_JWKS": "http://localhost:18180/realms/banking-lab/protocol/openid-connect/certs",
                    "OIDC_METADATA": "http://localhost:18180/realms/banking-lab/.well-known/openid-configuration",
                    "ASPNETCORE_ENVIRONMENT": "Development", "ASPNETCORE_URLS": "http://127.0.0.1:19081", "PORT": "19082",
                    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:19417"}
                if language == "csharp":
                    project = "Banking.Api" if mode == "ledger" else "Banking.Audit"
                    command = [args.dotnet, str(ROOT/"csharp"/project/"bin"/"Release"/"net10.0"/(project+".dll"))]
                else: command = [args.java, "-Xmx384m", "-jar", str(ROOT/"java"/"target"/"banking-lab-1.0.0.jar")]
                stream = (directory/(name+".log")).open("w", encoding="utf-8"); streams.append(stream)
                processes.append(subprocess.Popen(command, cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
        tests = ["integration_test.py", "recovery_test.py"]
        for test in tests:
            subprocess.run([sys.executable, "scripts/"+test], cwd=ROOT, env={**os.environ, "BANK_NATIVE_LOGS": str(directory)}, check=True)
        subprocess.run([sys.executable, "scripts/load_test.py", "--seed", "42", "--iterations", "80", "--pairs", "4", "--concurrency", "8"], cwd=ROOT, check=True)
        subprocess.run([sys.executable, "scripts/check_ledger_invariants.py"], cwd=ROOT, check=True)
        subprocess.run([sys.executable, "scripts/backup_restore_test.py"], cwd=ROOT, check=True)
    finally:
        for process in processes:
            if process.poll() is None: process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        for stream in streams: stream.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotnet", default="dotnet"); parser.add_argument("--java", default="java")
    parser.add_argument("--reuse-infrastructure", action="store_true", help="Use already running infrastructure with its topics initialized")
    verify(parser.parse_args())
