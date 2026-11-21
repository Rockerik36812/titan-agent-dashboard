"""Smoke test del panel de agentes.

No levanta el ciclo de fondo (TestClient sin context manager ⇒ sin evento de
startup), así que corre sin docker.sock ni acceso a los contenedores.
Cubre lo mínimo para no desplegar algo roto: que la app importe, que
/health y /api/auth/status respondan, que las APIs exijan sesión y que los
headers de seguridad vayan puestos.
"""
import os
import pathlib
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault("PANEL_APP_DIR", str(RAIZ))
os.environ.setdefault("PANEL_DATA_DIR", tempfile.mkdtemp(prefix="panel-test-"))
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

cliente = TestClient(main.app)


def test_health():
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert isinstance(r.json()["agents"], int)


def test_auth_status_responde():
    r = cliente.get("/api/auth/status")
    assert r.status_code == 200
    assert "configured" in r.json()


def test_apis_exigen_sesion():
    assert cliente.get("/api/agents").status_code == 401
    assert cliente.get("/api/analytics").status_code == 401


def test_headers_de_seguridad():
    h = cliente.get("/health").headers
    assert h.get("x-frame-options") == "DENY"
    assert h.get("x-content-type-options") == "nosniff"
    assert "frame-ancestors 'none'" in h.get("content-security-policy", "")


def test_index_redirige_al_login():
    r = cliente.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"


def test_sesion_vieja_recibe_csrf_nueva():
    """Sesión emitida antes del CSRF: el servidor le repone la cookie.

    Regresión real: al desplegar el CSRF, las sesiones ya abiertas se quedaron
    sin cookie `csrf_token` y todo POST (reiniciar agente, push) daba 403 hasta
    cerrar sesión a mano.
    """
    r = cliente.post("/api/auth/setup", json={"user": "prueba", "password": "PruebaSegura123"})
    if r.status_code == 400:      # ya hay contraseña en este directorio de datos
        r = cliente.post("/api/auth/login", json={"user": "prueba", "password": "PruebaSegura123"})
    assert r.status_code == 200, r.text
    assert "csrf_token" in cliente.cookies

    # simular navegador viejo: sesión válida pero sin la cookie CSRF
    cliente.cookies.delete("csrf_token")
    r = cliente.get("/", follow_redirects=False)
    assert "csrf_token" in r.headers.get("set-cookie", ""), "el servidor debe reponer la cookie"

    token = cliente.cookies.get("csrf_token")
    assert token
    r = cliente.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    assert r.status_code == 200, r.text