"""Verify that both API services exported real traces to the local Jaeger."""
import json
import os
import time
import urllib.request
import uuid

for service, base in [("ledger-csharp", os.environ.get("BASE_CSHARP", "http://127.0.0.1:19081")),
    ("ledger-java", os.environ.get("BASE_JAVA", "http://127.0.0.1:19082"))]:
    trace_id = uuid.uuid4().hex
    parent = uuid.uuid4().hex[:16]
    request = urllib.request.Request(base + "/health/live", headers={"traceparent": f"00-{trace_id}-{parent}-01"})
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
    for _ in range(120):
        try:
            with urllib.request.urlopen("http://127.0.0.1:19686/api/traces/" + trace_id, timeout=5) as response:
                traces = json.load(response)["data"]
            if any(process["serviceName"] == service for trace in traces for process in trace["processes"].values()):
                print(service + ": a newly generated trace reached Jaeger with its propagated trace ID")
                break
        except OSError:
            pass
        time.sleep(.5)
    else:
        raise SystemExit("Missing newly exported trace for " + service)
