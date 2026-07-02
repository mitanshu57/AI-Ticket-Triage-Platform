from httpx import AsyncClient

SAMPLE = {
    "subject": "Cannot log in",
    "body": "I get a 500 error when logging in since this morning.",
    "requester_email": "user@example.com",
}


async def test_create_ticket(client: AsyncClient):
    resp = await client.post("/api/v1/tickets", json=SAMPLE)
    assert resp.status_code == 201
    data = resp.json()
    assert data["subject"] == SAMPLE["subject"]
    assert data["status"] == "new"
    # AI fields are unset until the triage pipeline runs (Phase 2+).
    assert data["category"] is None
    assert data["priority"] is None
    assert "id" in data


async def test_get_ticket(client: AsyncClient):
    created = (await client.post("/api/v1/tickets", json=SAMPLE)).json()
    resp = await client.get(f"/api/v1/tickets/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_missing_ticket_404(client: AsyncClient):
    resp = await client.get("/api/v1/tickets/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_list_and_filter(client: AsyncClient):
    await client.post("/api/v1/tickets", json=SAMPLE)
    await client.post(
        "/api/v1/tickets",
        json={**SAMPLE, "subject": "Billing question"},
    )

    resp = await client.get("/api/v1/tickets")
    body = resp.json()
    assert resp.status_code == 200
    assert body["total"] == 2
    assert len(body["items"]) == 2

    # Filter by a status that no ticket has yet.
    resp = await client.get("/api/v1/tickets", params={"status": "resolved"})
    assert resp.json()["total"] == 0


async def test_update_ticket(client: AsyncClient):
    created = (await client.post("/api/v1/tickets", json=SAMPLE)).json()
    resp = await client.patch(
        f"/api/v1/tickets/{created['id']}",
        json={"status": "open", "priority": "high", "category": "auth"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "open"
    assert data["priority"] == "high"
    assert data["category"] == "auth"


async def test_delete_ticket(client: AsyncClient):
    created = (await client.post("/api/v1/tickets", json=SAMPLE)).json()
    resp = await client.delete(f"/api/v1/tickets/{created['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"/api/v1/tickets/{created['id']}")).status_code == 404


async def test_create_validation_error(client: AsyncClient):
    resp = await client.post(
        "/api/v1/tickets",
        json={"subject": "", "body": "x", "requester_email": "not-an-email"},
    )
    assert resp.status_code == 422
