import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.register import STORE

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_store():
    # Ensure STORE is empty before each test
    STORE.clear()
    yield
    STORE.clear()

def make_node(node_id: str):
    return {
        "id": node_id,
        "name": f"Tool {node_id}",
        "description": "A test tool",
        "prompt": "",
        "parameters": {}
    }

def test_list_contexts_empty():
    resp = client.get("/context")
    assert resp.status_code == 200
    # We always auto-seed the built-in "candidate_search"
    body = resp.json()
    ids = {t["id"] for t in body["tools"]}

    assert ids == {"candidate_search"}

def test_register_and_get_context():
    node = make_node("test1")
    # Register
    resp = client.post("/context", json=node)
    assert resp.status_code == 200
    assert resp.json() == node

    # Retrieve by ID
    resp2 = client.get(f"/context/{node['id']}")
    assert resp2.status_code == 200
    assert resp2.json() == node

def test_register_duplicate_fails():
    node = make_node("dup")
    resp1 = client.post("/context", json=node)
    assert resp1.status_code == 200

    resp2 = client.post("/context", json=node)
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"].lower()

def test_list_multiple_contexts():
    node1 = make_node("one")
    node2 = make_node("two")
    client.post("/context", json=node1)
    client.post("/context", json=node2)

    resp = client.get("/context")
    assert resp.status_code == 200

    tools = resp.json()["tools"]
    # Ensure both IDs are present
    ids = {t["id"] for t in tools}
    # Should include both user-registered plus the built-in
    assert ids == {"candidate_search", "one", "two"}
