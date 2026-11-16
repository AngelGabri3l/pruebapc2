import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["db"] == "ok"


def test_add_and_list_note(client):
    r = client.post("/add", data={"title": "nota de prueba ñandú"}, follow_redirects=True)
    assert r.status_code == 200
    assert "nota de prueba ñandú" in r.get_data(as_text=True)


def test_rejects_empty_title(client):
    r = client.post("/add", data={"title": "   "})
    assert r.status_code == 400


def test_rejects_too_long_title(client):
    r = client.post("/add", data={"title": "x" * 201})
    assert r.status_code == 400


def test_xss_is_escaped(client):
    payload = "<script>alert(1)</script>"
    client.post("/add", data={"title": payload})
    html = client.get("/").get_data(as_text=True)
    assert payload not in html
    assert "&lt;script&gt;" in html


def test_sql_injection_is_stored_as_text(client):
    payload = "x'); DROP TABLE notes; --"
    client.post("/add", data={"title": payload})
    r = client.get("/")
    assert r.status_code == 200  # la tabla sigue existiendo
