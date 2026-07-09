from fastapi.testclient import TestClient

from uam_territorial_suitability.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_criteria() -> None:
    response = client.get("/api/criteria")
    assert response.status_code == 200
    criteria = response.json()
    assert len(criteria) == 7
    assert {c["id"] for c in criteria} == {
        "geometry",
        "obstacles",
        "heliport_retrofit",
        "land_use",
        "proximity",
        "airspace_light",
        "topography",
    }
