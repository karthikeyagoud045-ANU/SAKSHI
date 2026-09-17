from fastapi.testclient import TestClient

from worker.main import app
from worker.store import reset_store


def test_given_dispatch_attempt_when_called_then_one_route_403_and_audit():
    store = reset_store()
    client = TestClient(app)

    response = client.post("/dispatch_attempt/ticket-1")

    assert sum("dispatch" in route.path for route in app.routes if hasattr(route, "path")) == 1
    assert response.status_code == 403
    assert response.json() == {"error": "policy_locked"}
    assert store.data["audit"][-1]["action"] == "policy_violation_blocked"
