from unittest.mock import patch


async def _mock_run_agent(address, buyer_context="", db=None, force_refresh=False):
    import json
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def _mock_run_agent_with_analysis_id(address, buyer_context="", db=None, force_refresh=False):
    import json
    yield f"data: {json.dumps({'type': 'status', 'text': 'Starting...'})}\n\n"
    yield f"data: {json.dumps({'type': 'analysis_id', 'id': 42})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


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


# --- /api/analyses endpoints ---

async def test_list_analyses_returns_empty_list(client):
    """GET /api/analyses returns 200 with empty list when no analyses saved."""
    resp = await client.get("/api/analyses")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_analysis_not_found(client):
    """GET /api/analyses/999 returns 404 when analysis doesn't exist."""
    resp = await client.get("/api/analyses/999")
    assert resp.status_code == 404


async def test_analyze_emits_analysis_id_event(client):
    """After a completed analysis, the SSE stream contains an analysis_id event."""
    with patch("api.routes.run_agent", _mock_run_agent_with_analysis_id):
        resp = await client.post("/api/analyze", json={
            "address": "450 Sanchez St, San Francisco, CA 94114"
        })
    assert resp.status_code == 200
    content = resp.text
    import json
    events = []
    for line in content.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    analysis_id_events = [e for e in events if e.get("type") == "analysis_id"]
    assert len(analysis_id_events) == 1
    assert analysis_id_events[0]["id"] == 42


async def test_force_refresh_field_accepted(client):
    """POST /api/analyze with force_refresh: true returns 200 (field is accepted)."""
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post("/api/analyze", json={
            "address": "450 Sanchez St, San Francisco, CA 94114",
            "force_refresh": True,
        })
    assert resp.status_code == 200
