import typing as t

import pytest

from flask import Flask
from pydantic import BaseModel

from server.api import helpers


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


import types
import typing as t

from server.const import USER_ROLES


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture


def view():
    return "ok"


def test_roles_required_grants_access(app: Flask, mocker: MockerFixture) -> None:
    """Tests roles_required decorator grants access for permitted role."""
    mocker.patch(
        "server.api.helpers.get_current_user_affiliations",
        return_value=([types.SimpleNamespace(role=USER_ROLES.SYSTEM_ADMIN)], None),
    )
    mocker.patch("server.api.helpers.get_highest_role", return_value=USER_ROLES.SYSTEM_ADMIN)

    result = helpers.roles_required(USER_ROLES.SYSTEM_ADMIN)(view)()
    assert result == "ok"


def test_roles_required_denies_access(app: Flask, mocker: MockerFixture) -> None:
    """Tests roles_required decorator denies access for non-permitted role."""
    mocker.patch(
        "server.api.helpers.get_current_user_affiliations",
        return_value=([types.SimpleNamespace(role=USER_ROLES.REPOSITORY_ADMIN)], None),
    )
    mocker.patch("server.api.helpers.get_highest_role", return_value=USER_ROLES.REPOSITORY_ADMIN)

    with pytest.raises(Exception, match="403"):
        helpers.roles_required(USER_ROLES.SYSTEM_ADMIN)(view)()


def test_validate_files_success_single(app: Flask, mocker: MockerFixture) -> None:
    """Tests validate_files passes with valid single file."""
    file_storage = mocker.Mock()
    file_storage.seek.side_effect = lambda *_, **__: None
    file_storage.tell.return_value = 100

    class FileModel(BaseModel):
        file: t.Any

    def view(files: FileModel):
        return files.file

    with app.test_request_context():
        mock_request = mocker.patch("server.api.helpers.request")
        mock_request.files = {"file": file_storage}
        result = helpers.validate_files(view)()
        assert result == file_storage


def test_validate_files_success(app: Flask, mocker: MockerFixture) -> None:
    class FileModel(BaseModel):
        file: t.Any

    file_storage = mocker.MagicMock()
    file_storage.seek.side_effect = lambda *_, **__: None
    file_storage.tell.return_value = 100

    def view(files: FileModel):
        return files.file

    with app.test_request_context():
        mock_request = mocker.patch("server.api.helpers.request")

        mock_request.files = {"file": file_storage}
        result = helpers.validate_files(view)()
        assert result == file_storage


def test_validate_files_missing_field(app: Flask, mocker: MockerFixture) -> None:
    expected_status_code = 400

    class FileModel(BaseModel):
        file: t.Any

    mocker.patch("server.api.helpers.config.API.max_upload_size", 200)

    def view(files: FileModel):
        return files.file

    with app.test_request_context():
        mock_request = mocker.patch("server.api.helpers.request")

        mock_request.files = {}
        response = helpers.validate_files(view)()
        assert response.status_code == expected_status_code
        assert "validation_error" in response.json


def test_validate_files_validation_error(app: Flask, mocker: MockerFixture) -> None:
    class InvalidModel(BaseModel):
        file: int

    file_storage = mocker.MagicMock()
    file_storage.seek.side_effect = lambda *_, **__: None
    file_storage.tell.return_value = 100
    mocker.patch("server.api.helpers.config.API.max_upload_size", 200)

    def view(files: InvalidModel):
        return files.file

    with app.test_request_context():
        mock_request = mocker.patch("server.api.helpers.request")

        mock_request.files = {"file": file_storage}
        response = helpers.validate_files(view)()
        assert response == 1


def test_validate_files_file_size_key_already_in_err(app: Flask, mocker: MockerFixture) -> None:
    """Covers the False branch of 'if "file_size" not in err:' (file_size already in err)."""
    expected_status_code = 400

    class FileModel(BaseModel):
        file: t.Any

    def view(files: FileModel):
        return files.file

    helpers.validate_files(view)
    file_storage = mocker.Mock()
    file_storage.seek.side_effect = lambda *_, **__: None
    file_storage.tell.return_value = 300
    mocker.patch("server.api.helpers.config.API.max_upload_size", 200)
    mocker.patch("server.api.helpers._check_file_size", return_value=[{"type": "value_error.filesize_limit"}])

    with app.test_request_context():
        mock_request = mocker.patch("server.api.helpers.request")
        mock_request.files = {"file": file_storage}

        mock_request.files = {"file": file_storage, "file2": file_storage}
        mocker.patch(
            "server.api.helpers._check_file_size",
            side_effect=[[{"type": "value_error.filesize_limit"}], [{"type": "value_error.filesize_limit"}]],
        )

        class FileModel2(BaseModel):
            file: t.Any
            file2: t.Any

        def view2(files: FileModel2):
            return files.file

        wrapper2 = helpers.validate_files(view2)
        response = wrapper2()
        assert hasattr(response, "status_code")
        assert response.status_code == expected_status_code
        assert "validation_error" in response.json


def test_validate_files_files_in_kwargs_annotation_false_value(app: Flask, mocker: MockerFixture) -> None:
    """Covers the False branch where files_in_kwargs is explicitly set to False in __annotations__."""
    files_model_mock = mocker.patch("server.api.helpers._check_file_size", autospec=True)

    def view(files=None):
        return "files_in_kwargs is False"

    view.__annotations__["files"] = False

    wrapper = helpers.validate_files(view)
    with app.test_request_context():
        result = wrapper()
        assert result == "files_in_kwargs is False"
        files_model_mock.assert_not_called()


def test_check_file_size_under_limit(app: Flask, mocker: MockerFixture) -> None:
    """Tests _check_file_size returns empty list for file under limit."""
    file_mock = mocker.Mock()
    file_mock.tell.return_value = 100
    file_mock.seek.side_effect = lambda *_, **__: None
    mocker.patch("server.api.helpers.config.API.max_upload_size", 200)
    errors = helpers._check_file_size("file", file_mock)  # noqa: SLF001
    assert errors == []


def test_check_file_size_over_limit(app: Flask, mocker: MockerFixture) -> None:
    """Tests _check_file_size returns error for file over limit."""
    expected_actual_value = 300
    expected_limit_value = 200
    file_mock = mocker.Mock()
    file_mock.tell.return_value = expected_actual_value
    file_mock.seek.side_effect = lambda *_, **__: None
    mocker.patch("server.api.helpers.config.API.max_upload_size", expected_limit_value)
    errors = helpers._check_file_size("file", file_mock)  # noqa: SLF001
    assert errors[0]["type"] == "value_error.filesize_limit"
    assert errors[0]["ctx"]["actual_value"] == expected_actual_value
    assert errors[0]["ctx"]["limit_value"] == expected_limit_value


def test_check_file_size_continue_branches(app: Flask) -> None:
    result = helpers._check_file_size("file", None)  # noqa: SLF001
    assert result == []
