from app.main import create_app


def test_health_endpoint_returns_service_status() -> None:
    app = create_app()
    app.config["APP_NAME"] = "Test API"

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "Test API"}
