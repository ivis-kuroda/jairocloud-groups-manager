from flask import Flask


def test_app_initialization():
    from server.app import app  # noqa: PLC0415

    assert isinstance(app, Flask)
    assert app.extensions["sqlalchemy"] is not None
    assert app.extensions["jairocloud-groups-manager"] is not None
