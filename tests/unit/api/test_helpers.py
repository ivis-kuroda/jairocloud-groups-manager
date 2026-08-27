import typing as t

from http import HTTPStatus
from io import BytesIO

import pytest

from flask import Flask, make_response
from flask_login import login_user
from flask_pydantic import validate
from pydantic import BaseModel, ConfigDict
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import Forbidden, Unauthorized

import server.api.helpers

from server.api.helpers import _check_file_size, roles_required, validate_files
from server.const import USER_ROLES
from server.messages import E

from tests.helpers import assert_message, regex


if t.TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from server.config import RuntimeConfig
    from server.entities.login_user import LoginUser


def test_roles_required(app: Flask, login_users, user_affils, mocker: MockerFixture):
    required = USER_ROLES.SYSTEM_ADMIN
    user: LoginUser = login_users[required]
    mocker.patch.object(server.api.helpers, "is_user_logged_in", return_value=True)
    mock_detect = mocker.patch.object(server.api.helpers, "detect_affiliations_from_is_member_of")
    mock_detect.return_value = user_affils[required]
    mock_highest = mocker.patch.object(server.api.helpers, "get_highest_role", return_value=required)

    with app.test_request_context():
        login_user(user)

        res = roles_required(required)(simple_view)()

    assert res.status_code == HTTPStatus.OK
    assert res.get_data(as_text=True) == "ok"
    mock_detect.assert_called_once_with(user.is_member_of)
    mock_highest.assert_called_once_with([required])


def test_roles_required_model_view(app: Flask, login_users, user_affils, mocker: MockerFixture):
    required = USER_ROLES.SYSTEM_ADMIN
    user: LoginUser = login_users[required]
    mocker.patch.object(server.api.helpers, "is_user_logged_in", return_value=True)
    mock_detect = mocker.patch.object(server.api.helpers, "detect_affiliations_from_is_member_of")
    mock_detect.return_value = user_affils[required]
    mock_highest = mocker.patch.object(server.api.helpers, "get_highest_role", return_value=required)

    body = TestModel(type="request", message=HTTPStatus.OK.phrase)
    expected = TestModel(type="response", message=HTTPStatus.OK.phrase)

    with app.test_request_context(method="POST", json=body.model_dump(mode="json")):
        login_user(user)

        res = roles_required(required)(model_view)()

    assert res.status_code == HTTPStatus.OK
    assert res.json == expected.model_dump(mode="json")
    mock_detect.assert_called_once_with(user.is_member_of)
    mock_highest.assert_called_once_with([required])


def test_roles_required_unauthorized(app: Flask, login_users, mocker: MockerFixture):
    required = USER_ROLES.SYSTEM_ADMIN
    user: LoginUser = login_users[required]
    mocker.patch.object(server.api.helpers, "is_user_logged_in", return_value=False)

    with app.test_request_context():
        login_user(user)

        with pytest.raises(Unauthorized, match=regex(E.UNAUTHORIZED)):
            roles_required(required)(simple_view)()


def test_roles_required_forbidden(app: Flask, login_users, user_affils, mocker: MockerFixture):
    required, client = USER_ROLES.SYSTEM_ADMIN, USER_ROLES.REPOSITORY_ADMIN
    user: LoginUser = login_users[client]
    mocker.patch.object(server.api.helpers, "is_user_logged_in", return_value=True)
    mocker.patch.object(server.api.helpers, "detect_affiliations_from_is_member_of", return_value=user_affils[client])
    mocker.patch.object(server.api.helpers, "get_highest_role", return_value=client)

    with app.test_request_context():
        login_user(user)

        with pytest.raises(Forbidden, match=regex(E.FORBIDDEN)):
            roles_required(required)(simple_view)()


def test_validate_files(app: Flask, config: RuntimeConfig):
    content = b"test file content"
    mock_file = BytesIO(content)

    config.API.max_upload_size = 200 + len(content)

    with app.test_request_context(
        method="POST", data={"file": (mock_file, "test.txt")}, content_type="multipart/form-data"
    ):
        res = validate_files(file_view)()

        assert res.get_data() == content

    assert res.status_code == HTTPStatus.OK


def test_validate_files_multiple(app: Flask, config: RuntimeConfig):
    content1, content2 = b"test file content 1", b"test file content 2"
    mock_file1, mock_file2 = BytesIO(content1), BytesIO(content2)
    config.API.max_upload_size = 200 + len(content1)

    with app.test_request_context(
        method="POST",
        data={"files": [(mock_file1, "test1.txt"), (mock_file2, "test2.txt")]},
        content_type="multipart/form-data",
    ):
        res = validate_files(files_view)()

    assert res.status_code == HTTPStatus.OK
    assert res.get_data() == content1 + b";" + content2


def test_validate_files_multiple_key(app: Flask, config: RuntimeConfig):
    content1, content2 = b"test file content 1", b"test file content 2"
    mock_file1, mock_file2 = BytesIO(content1), BytesIO(content2)

    config.API.max_upload_size = 200 + len(content1)

    with app.test_request_context(
        method="POST",
        data={"file1": (mock_file1, "test1.txt"), "file2": (mock_file2, "test2.txt")},
        content_type="multipart/form-data",
    ):
        res = validate_files(multiple_key_file_view)()

        assert res.status_code == HTTPStatus.OK
        assert res.get_data() == content1 + b";" + content2


def test_validate_files_no_file(app: Flask, config: RuntimeConfig):
    config.API.max_upload_size = 200

    with app.test_request_context():
        res = validate_files(file_view)()

    assert res.status_code == HTTPStatus.BAD_REQUEST
    assert "file_params" in res.json["validation_error"]


def test_validate_files_validation_error(app: Flask, config: RuntimeConfig):
    file_content = b"test file content"
    mock_file = BytesIO(file_content)
    config.API.max_upload_size = 200

    with app.test_request_context(
        method="POST", data={"invalid_key": (mock_file, "test.txt")}, content_type="multipart/form-data"
    ):
        res = validate_files(file_view)()

    assert res.status_code == HTTPStatus.BAD_REQUEST
    assert "file_params" in res.json["validation_error"]


def test_validate_files_too_large(app: Flask, config: RuntimeConfig):
    file_content = b"test file content" * 20
    mock_file = BytesIO(file_content)
    config.API.max_upload_size = 200

    with app.test_request_context(
        method="POST", data={"file": (mock_file, "test.txt")}, content_type="multipart/form-data"
    ):
        res = validate_files(file_view)()

    assert res.status_code == HTTPStatus.BAD_REQUEST
    assert "file_size" in res.json["validation_error"]


def test_validate_files_multiple_too_large(app: Flask, config: RuntimeConfig):
    file_content = b"test file content" * 20
    mock_file1, mock_file2 = BytesIO(file_content), BytesIO(file_content)
    config.API.max_upload_size = 200
    num_files = 2

    with app.test_request_context(
        method="POST",
        data={"file1": (mock_file1, "test1.txt"), "file2": (mock_file2, "test2.txt")},
        content_type="multipart/form-data",
    ):
        res = validate_files(multiple_key_file_view)()

    assert res.status_code == HTTPStatus.BAD_REQUEST
    assert "file_size" in res.json["validation_error"]
    assert len(res.json["validation_error"]["file_size"]) == num_files


def test_validate_files_files_in_kwargs_annotation_false_value(app: Flask, mocker: MockerFixture):
    mock_check = mocker.patch.object(server.api.helpers, "_check_file_size")

    with app.test_request_context():
        res = validate_files(no_file_view)()

    assert res.status_code == HTTPStatus.OK
    assert res.get_data(as_text=True) == "ok"
    mock_check.assert_not_called()


def test__check_file_size(config: RuntimeConfig, mocker: MockerFixture):
    max_size, actual_size = 200, 100
    config.API.max_upload_size = max_size
    file_mock = mocker.Mock()
    file_mock.tell.return_value = actual_size

    assert not _check_file_size("file", file_mock)


def test__check_file_size_too_large(config: RuntimeConfig, mocker: MockerFixture):
    max_size, actual_size = 200, 300
    config.API.max_upload_size = max_size
    file_mock = mocker.Mock()
    file_mock.tell.return_value = actual_size
    field_name = "file"

    result = _check_file_size(field_name, file_mock)

    error = result[0]
    assert error["loc"] == [field_name]
    assert error["type"] == "value_error.filesize_limit"
    assert error["ctx"]["actual_value"] == actual_size
    assert error["ctx"]["limit_value"] == max_size
    assert_message(error["msg"], E.FILE_TOO_LARGE % {"max": max_size})


def test__check_file_size_no_files(config):
    result = _check_file_size("file", None)
    assert not result


class TestModel(BaseModel):
    type: t.Literal["request", "response"]
    message: str


class TestFileModel(BaseModel):
    file: FileStorage
    model_config = ConfigDict(arbitrary_types_allowed=True)


class TestMultipleFilesModel(BaseModel):
    files: list[FileStorage]
    model_config = ConfigDict(arbitrary_types_allowed=True)


class TestMultiplekeyFilesModel(BaseModel):
    file1: FileStorage
    file2: FileStorage
    model_config = ConfigDict(arbitrary_types_allowed=True)


def simple_view():
    return make_response("ok", HTTPStatus.OK)


@validate()
def model_view(body: TestModel):
    return TestModel(type="response", message=body.message)


def file_view(files: TestFileModel):
    return make_response(files.file.stream, HTTPStatus.OK)


def files_view(files: TestMultipleFilesModel):
    return make_response(b";".join([file.read() for file in files.files]), HTTPStatus.OK)


def multiple_key_file_view(files: TestMultiplekeyFilesModel):
    return make_response(
        b";".join([files.file1.read(), files.file2.read()]),
        HTTPStatus.OK,
    )


def no_file_view(files: None = None):
    return make_response("ok", HTTPStatus.OK)
