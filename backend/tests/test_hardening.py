"""Hardening checks of slice 6: response headers and the timing of failed logins (LCK-011)."""
from __future__ import annotations

import statistics
import time

from tests.conftest import Env


def test_security_headers_are_on_every_response(env: Env):
    for path in ("/api/v1/health", "/api/v1/auth/session", "/definitely-not-a-page"):
        r = env.client.get(path)
        csp = r.headers["content-security-policy"]
        assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
        script = next(part for part in csp.split(";") if part.strip().startswith("script-src"))
        assert "unsafe-inline" not in script and "unsafe-eval" not in script
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert "geolocation=()" in r.headers["permissions-policy"]
    assert env.client.get("/api/v1/health").headers["cache-control"] == "no-store"


def test_websocket_origin_is_allowed_by_the_policy(env: Env):
    csp = env.client.get("/api/v1/health", headers={"host": "ops.example.test:8443"}).headers["content-security-policy"]
    assert "ws://ops.example.test:8443" in csp and "wss://ops.example.test:8443" in csp


def test_failed_login_takes_about_as_long_for_unknown_and_known_users(env: Env):
    """An attacker must not be able to tell a real user name from the time of the answer (LCK-011).
    Indicative, not a proof: the medians of 12 failures each are compared with a generous bound."""
    for i in range(12):
        env.make_user(f"timing{i}", "SOC Operator")
    known, unknown = [], []
    for i in range(12):
        start = time.perf_counter()
        env.login(f"timing{i}", "Wrong-password-1!x")
        known.append(time.perf_counter() - start)
        start = time.perf_counter()
        env.login(f"nobody{i}", "Wrong-password-1!x")
        unknown.append(time.perf_counter() - start)
    k, u = statistics.median(known), statistics.median(unknown)
    print(f"login failure median: known user {k * 1000:.0f} ms, unknown user {u * 1000:.0f} ms")
    assert 0.5 < u / k < 2.0, (k, u)
