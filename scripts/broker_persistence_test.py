"""Verify that broker recreation preserves topic identities and record offsets."""
import json
from pathlib import Path
import re
import subprocess
import time

root = Path(__file__).resolve().parents[1]
def run(*command):
    return subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout

def describe():
    output = run("docker", "compose", "exec", "-T", "kafka", "/opt/kafka/bin/kafka-topics.sh",
        "--bootstrap-server", "localhost:29092", "--describe")
    identities = dict(re.findall(r"Topic: (\S+)\s+TopicId: (\S+)", output))
    assert all(topic in identities for topic in ("transfers.csharp.v1", "transfers.java.v1", "__consumer_offsets")), output
    return identities

def offsets():
    output = run("docker", "compose", "exec", "-T", "kafka", "/opt/kafka/bin/kafka-get-offsets.sh",
        "--bootstrap-server", "localhost:29092", "--topic", "transfers.*.v1", "--time", "-1")
    return {topic + ":" + partition: int(offset) for topic, partition, offset in
        (line.split(":") for line in output.splitlines() if line.startswith("transfers."))}

before = describe()
before_offsets = offsets()
assert len(before_offsets) == 6, before_offsets
run("docker", "compose", "up", "-d", "--no-deps", "--force-recreate", "kafka")
deadline = time.monotonic() + 300
while time.monotonic() < deadline:
    container = json.loads(run("docker", "inspect", "banking-lab-kafka-1"))[0]
    if container["State"]["Health"]["Status"] == "healthy":
        break
    time.sleep(2)
else:
    raise AssertionError("Recreated broker did not become healthy")
after = describe()
assert before == after, (before, after)
after_offsets = offsets()
assert all(after_offsets.get(key, -1) >= value for key, value in before_offsets.items()), (before_offsets, after_offsets)
print("Broker recreated: topic identities and record offsets persisted across all six application partitions.")
