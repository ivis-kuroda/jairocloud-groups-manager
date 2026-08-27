from flask import Flask


def test_app_initialization():
    from server.app import app  # ruff: ignore[import-outside-top-level]

    assert isinstance(app, Flask)
    assert app.extensions["sqlalchemy"] is not None
    assert app.extensions["jairocloud-groups-manager"] is not None
