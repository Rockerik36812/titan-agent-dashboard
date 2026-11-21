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