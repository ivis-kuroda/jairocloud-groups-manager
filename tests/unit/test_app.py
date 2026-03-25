from server.app import app


def test_app_initialization():
    """Tests that the Flask app is initialized correctly."""

    assert app is not None
    assert hasattr(app, "config")
