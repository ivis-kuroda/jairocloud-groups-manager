from celery import Celery


def test_celery_app_initialization(sqlalchemy_disable, redis_disable):
    """Tests that the Celery app is initialized correctly."""
    from server.celery_app import celery_app  # noqa: PLC0415

    assert isinstance(celery_app, Celery)
