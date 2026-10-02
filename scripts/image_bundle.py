"""Export and promote the exact tested Docker images; never rebuild in release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
IMAGES = {"ledger-csharp": "banking-ledger-csharp:local", "audit-csharp": "banking-audit-csharp:local", "java": "banking-java:local"}

def run(*args):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""): digest.update(chunk)
    return digest.hexdigest()

def identity(image):
    return run("docker", "image", "inspect", "--format", "{{.Id}}", image)

def validate(directory, commit, run_id, repository):
    manifest = json.loads((directory / "manifest.json").read_text())
    if not re.fullmatch(r"[0-9a-f]{40}", commit): raise ValueError("Invalid commit")
    if (manifest["commit"], manifest["runId"], manifest["repository"]) != (commit, run_id, repository): raise ValueError("Bundle is from another commit or workflow run")
    if len(manifest["images"]) != len(IMAGES) or {item["name"]: item["image"] for item in manifest["images"]} != IMAGES: raise ValueError("Unexpected image set")
    for item in manifest["files"]:
        name = item["name"]
        if Path(name).name != name or any(character in name for character in ("/", "\\", ":")) or name in (".", ".."): raise ValueError("Invalid bundle path")
        if sha256(directory / name) != item["sha256"]: raise ValueError("Bundle checksum mismatch: " + name)
    required = {"banking-images.tar", *(name + ".cdx.json" for name in IMAGES)}
    if {item["name"] for item in manifest["files"]} != required: raise ValueError("Incomplete bundle")
    for item in manifest["images"]:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", item["imageId"]): raise ValueError("Invalid image identity")
        sbom = json.loads((directory / (item["name"] + ".cdx.json")).read_text())
        if sbom.get("bomFormat") != "CycloneDX": raise ValueError("Invalid SBOM")
    return manifest

def export(directory, commit, run_id, repository):
    directory.mkdir(parents=True, exist_ok=True)
    cache = ROOT.parent / ".tools" / "trivy-cache"
    cache.mkdir(parents=True, exist_ok=True)
    images = [{"name": name, "image": image, "imageId": identity(image)} for name, image in IMAGES.items()]
    for item in images:
        services = ["ledger-java", "audit-java"] if item["name"] == "java" else [item["name"]]
        for service in services:
            container = run("docker", "compose", "ps", "-q", service)
            if not container or run("docker", "inspect", "--format", "{{.Image}} {{.State.Running}}", container) != item["imageId"]+" true":
                raise ValueError("Image differs from the running tested container: "+service)
        report_name = "csharp" if item["name"] == "ledger-csharp" else item["name"]
        scan = json.loads((ROOT/"artifacts"/"security"/("trivy-"+report_name+".json")).read_text())
        if scan.get("Metadata", {}).get("ImageID") != item["imageId"]: raise ValueError("Image differs from the security scan")
        if any(finding["Severity"] in ("HIGH", "CRITICAL") for result in scan.get("Results", []) for finding in result.get("Vulnerabilities", [])):
            raise ValueError("Security scan did not pass")
    for name, image in IMAGES.items():
        run("docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock", "-v", cache.as_posix()+":/root/.cache/trivy",
            "-v", directory.as_posix()+":/reports", "aquasec/trivy:0.75.0", "image", "--timeout", "15m", "--format", "cyclonedx", "--output", "/reports/"+name+".cdx.json", image)
    run("docker", "image", "save", "-o", str(directory / "banking-images.tar"), *IMAGES.values())
    if any(identity(item["image"]) != item["imageId"] for item in images): raise ValueError("Image changed during bundle creation")
    files = [{"name": name, "sha256": sha256(directory / name)} for name in ["banking-images.tar", *(name+".cdx.json" for name in IMAGES)]]
    manifest = {"version": 1, "commit": commit, "runId": run_id, "repository": repository, "images": images, "files": files}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    validate(directory, commit, run_id, repository)
    print("Exported three tested images with their IDs, archive checksum and CycloneDX SBOMs.")

def promote(directory, commit, run_id, repository, dry_run):
    if not re.fullmatch(r"[a-z0-9_.-]+/[a-z0-9_.-]+", repository): raise ValueError("Invalid repository")
    manifest = validate(directory, commit, run_id, repository)
    run("docker", "image", "load", "-i", str(directory / "banking-images.tar"))
    promoted = []
    for item in manifest["images"]:
        if identity(item["image"]) != item["imageId"]: raise ValueError("Loaded image differs from tested image")
        target = "ghcr.io/"+repository+"/"+item["name"]+":"+commit
        if dry_run:
            promoted.append({**item, "target": target}); continue
        run("docker", "image", "tag", item["image"], target)
        run("docker", "image", "push", target)
        digests = json.loads(run("docker", "image", "inspect", "--format", "{{json .RepoDigests}}", target))
        matching = [value for value in digests if value.startswith(target.split(":")[0]+"@sha256:")]
        if len(matching) != 1: raise ValueError("Missing immutable registry digest")
        run("docker", "image", "pull", matching[0])
        if identity(matching[0]) != item["imageId"]: raise ValueError("Registry image differs from tested image")
        digest = matching[0].split("@")[1]
        promoted.append({**item, "target": target, "registryDigest": digest})
        if os.getenv("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as stream: stream.write(item["name"].replace("-", "_")+"_digest="+digest+"\n")
    (directory / "promotion.json").write_text(json.dumps({"commit": commit, "runId": run_id, "dryRun": dry_run, "images": promoted}, indent=2)+"\n", encoding="utf-8")
    print("Verified loaded image identities; " + ("dry run completed." if dry_run else "registry images match the tested images."))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["export", "promote"])
    parser.add_argument("--directory", type=Path, default=ROOT/"artifacts"/"images")
    parser.add_argument("--commit", default=os.getenv("GITHUB_SHA"))
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", "jorgefprietol/banking-architecture-lab"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.commit: parser.error("A commit is required")
    if args.mode == "export": export(args.directory.resolve(), args.commit, args.run_id, args.repository)
    else: promote(args.directory.resolve(), args.commit, args.run_id, args.repository, args.dry_run)
