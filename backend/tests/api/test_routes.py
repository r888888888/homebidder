import pytest
from pydantic import ValidationError
from unittest.mock import patch


async def _mock_run_agent(address, buyer_context=""):
    import json
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# --- AnalyzeRequest model ---

def test_analyze_request_accepts_address():
    from api.routes import AnalyzeRequest
    req = AnalyzeRequest(address="450 Sanchez St, San Francisco, CA 94114")
    assert req.address == "450 Sanchez St, San Francisco, CA 94114"


def test_analyze_request_buyer_context_defaults_to_empty():
    from api.routes import AnalyzeRequest
    req = AnalyzeRequest(address="450 Sanchez St, San Francisco, CA 94114")
    assert req.buyer_context == ""


def test_analyze_request_rejects_missing_address():
    from api.routes import AnalyzeRequest
    with pytest.raises(ValidationError):
        AnalyzeRequest()


def test_analyze_request_rejects_url_field():
    from api.routes import AnalyzeRequest
    with pytest.raises(ValidationError):
        AnalyzeRequest(url="https://zillow.com/foo")


# --- /api/analyze endpoint ---

async def test_analyze_endpoint_accepts_address(client):
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post("/api/analyze", json={
            "address": "450 Sanchez St, San Francisco, CA 94114"
        })
    assert resp.status_code == 200


async def test_analyze_endpoint_rejects_missing_address(client):
    resp = await client.post("/api/analyze", json={"buyer_context": "quick close"})
    assert resp.status_code == 422


async def test_analyze_endpoint_rejects_url_payload(client):
    resp = await client.post("/api/analyze", json={"url": "https://zillow.com/foo"})
    assert resp.status_code == 422
