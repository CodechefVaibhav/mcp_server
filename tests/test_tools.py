import json
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Open the SSE stream and read all lines before it closes.
def test_candidate_search_sse_stream():
    # define the actual query parameters here
    qp = {"experience": 3, "location": "Delhi", "department": "HR"}
    with client.stream(
        "GET",
        "/tools/candidate/search/sse",
        params=qp
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Read lines while the stream is open
        lines = []
        for raw in resp.iter_lines():
            if not raw or not raw.strip():
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            lines.append(line)

    # Expect four lines: event/prompt, data/prompt, event/results, data/results
      # strip off any trailing newline when comparing
    assert lines[0].strip() == "event: prompt"
    assert lines[1].startswith("data: Find candidates with at least 3 years")
    # strip off any trailing newline when comparing
    assert lines[2].strip() == "event: results"
    # The data line is JSON for the list of candidates
    assert lines[3].startswith("data: ")
    # Parse out JSON and verify it’s a list of dicts
    payload = json.loads(lines[3][len("data: "):])
    assert isinstance(payload, list)
    # For HR@Delhi with exp>=3, Bob should match
    assert any(c["name"] == "Bob" for c in payload)

def test_tools_health_and_discovery():
    # Health
    h = client.get("/health")
    assert h.status_code == 200
    assert h.json() == {"status": "ok"}

    # Discovery: should at least contain the built-in candidate_search
    d = client.get("/.well-known/mcp.json")
    assert d.status_code == 200
    body = d.json()
    assert "tools" in body
    ids = {t["id"] for t in body["tools"]}
    assert "candidate_search" in ids
