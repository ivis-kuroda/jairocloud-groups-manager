from server.celery_app import celery_app


def test_celery_app_initialization():
    """Tests that the Celery app is initialized correctly."""

    assert celery_app is not None
    assert hasattr(celery_app, "send_task")
