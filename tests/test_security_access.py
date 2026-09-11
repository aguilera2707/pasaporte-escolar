import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from app import app, db
from app.models import Familia


def setup_module():
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add_all([
            Familia(nombre="Familia Uno", correo="uno@example.com", password="uno", puntos=10),
            Familia(nombre="Familia Dos", correo="dos@example.com", password="dos", puntos=20),
        ])
        db.session.commit()


def familia_session(client, familia_id):
    with client.session_transaction() as session:
        session.clear()
        session["familia_id"] = familia_id
        session["rol"] = "familia"


def staff_session(client, rol="admin"):
    with client.session_transaction() as session:
        session.clear()
        session["admin_id"] = 1
        session["rol"] = rol


def test_unauthenticated_family_page_redirects_to_login():
    response = app.test_client().get("/familia/1/ver")
    assert response.status_code == 302
    assert "/login_familia" in response.headers["Location"]


def test_family_can_access_own_page_but_not_another_family():
    client = app.test_client()
    familia_session(client, 1)
    assert client.get("/familia/1/ver").status_code == 200
    assert client.get("/familia/2/ver").status_code == 403
    assert client.get("/familia/2/historial").status_code == 403
    assert client.get("/familia/2/exportar").status_code == 403


def test_staff_keeps_authorized_cross_family_access():
    client = app.test_client()
    staff_session(client, "supervisor")
    assert client.get("/familia/1/ver").status_code == 200
    assert client.get("/familia/2/ver").status_code == 200


def test_point_mutations_are_not_public():
    client = app.test_client()
    assert client.post("/sumar_puntos", json={"familia_id": 1, "puntos": 5}).status_code == 302
    assert client.post("/familias/1/puntos", json={"puntos": 5}).status_code == 302
    assert client.post("/familia/1/transaccion", json={"tipo": "suma", "puntos": 5}).status_code == 302


def test_family_list_does_not_expose_passwords():
    client = app.test_client()
    staff_session(client)
    response = client.get("/familias")
    assert response.status_code == 200
    assert all("password" not in family for family in response.get_json())


def test_legacy_static_family_qr_is_blocked():
    response = app.test_client().get("/static/qr/familia_1.png")
    assert response.status_code == 404
