from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_world.worlds.static_routes import register_static_routes


def app_with_files(tmp_path):
    (tmp_path / "index.html").write_text("<main>front door</main>")
    (tmp_path / "sw.js").write_text("self.addEventListener('push', () => {});")
    (tmp_path / "manifest.webmanifest").write_text('{"name":"Worlds"}')
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("export {}")
    app = FastAPI()
    @app.get("/healthz")
    def health():
        return {"ok": True}
    register_static_routes(app, tmp_path)
    return TestClient(app)


def test_pwa_headers_and_spa_fallback(tmp_path):
    client = app_with_files(tmp_path)
    sw = client.get("/sw.js")
    assert sw.status_code == 200 and sw.headers["content-type"].startswith("text/javascript")
    assert sw.headers["service-worker-allowed"] == "/" and sw.headers["cache-control"] == "no-cache"
    assert client.get("/manifest.webmanifest").headers["content-type"].startswith("application/manifest+json")
    assert client.get("/settings").text == "<main>front door</main>"
    assert client.get("/settings").headers["cache-control"] == "no-cache"


def test_api_and_traversals_are_not_served_as_spa(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    client = app_with_files(static)
    missing = client.get("/api/nope")
    assert missing.status_code == 404 and missing.headers["content-type"].startswith("application/json")
    (tmp_path / "outside.txt").write_text("outside-the-static-dir")
    # The HTTP client may normalise dot segments before sending (then the SPA index is a correct answer); whatever
    # reaches the server, no attempt may ever return a file from outside the static directory.
    for url in ("/../outside.txt", "/%2e%2e/outside.txt", "/assets/../../outside.txt", "/assets/%2e%2e/%2e%2e/outside.txt",
                "/..%2foutside.txt", "/assets/..%5c..%5coutside.txt"):
        r = client.get(url)
        assert r.status_code in (200, 404) and "outside-the-static-dir" not in r.text, url
        if r.status_code == 200:
            assert r.text == "<main>front door</main>", url
    # An encoded dot segment that does reach the server is refused outright.
    assert client.get("/%2e%2e/outside.txt").status_code == 404
    (static / "escape.png").symlink_to(tmp_path / "outside.txt")
    assert client.get("/escape.png").status_code == 404


def test_missing_index_returns_503(tmp_path):
    app = FastAPI()
    register_static_routes(app, tmp_path)
    assert TestClient(app).get("/").status_code == 503


def test_index_symlink_cannot_escape_static_directory(tmp_path):
    outside = tmp_path.parent / "private-index.html"
    outside.write_text("private")
    (tmp_path / "index.html").symlink_to(outside)
    app = FastAPI()
    register_static_routes(app, tmp_path)
    response = TestClient(app).get("/")
    assert response.status_code == 404 and "private" not in response.text
