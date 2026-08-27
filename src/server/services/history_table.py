#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing history table."""

import typing as t

from datetime import UTC, datetime
from uuid import UUID  # ruff: ignore[typing-only-standard-library-import]

from flask import current_app
from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from server.db import db
from server.db.history import (
    DownloadHistory,
    Files,
    ResultStatus,
    UploadHistory,
    _FileContent,
    _ResultData,
)
from server.exc import (
    DatabaseError,
    InvalidQueryError,
    RecordNotFound,
)
from server.messages import E


if t.TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult
    from sqlalchemy.sql.elements import TableValuedColumn

    from server.entities.bulk import FileContent, ValidateResults


def get_upload_by_id(history_id: UUID) -> UploadHistory | None:
    """Get an upload history record by its ID.

    Args:
        history_id (UUID): The ID of the upload history.

    Returns:
        UploadHistory | None: The upload history record, or None if not found.

    Raises:
        DatabaseError: If there is an error querying the database.
    """
    try:
        history = db.session.get(
            UploadHistory, history_id, options=[selectinload(UploadHistory.file)]
        )
    except SQLAlchemyError as exc:
        current_app.logger.error(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD, {"history_id": history_id}
        )
        raise DatabaseError(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id}
        ) from exc
    return history


@t.overload
def get_upload_results(history_id: UUID, attribute: t.Literal["summary"]) -> dict: ...
@t.overload
def get_upload_results(
    history_id: UUID, attribute: t.Literal["items", "missing_users"]
) -> list[dict]: ...
def get_upload_results(
    history_id: UUID, attribute: t.Literal["summary", "items", "missing_users"]
) -> dict | list[dict]:
    """Get upload results by history ID and attribute.

    Args:
        history_id (UUID): The ID of the upload history.
        attribute (Literal["summary", "items", "missing_users"]):
            The attribute to retrieve from results.

    Returns:
        dict | list[dict]: The upload results for the specified attribute.

    Raises:
        DatabaseError: If there is an error querying the database.
        RecordNotFound: If no history record is found for the given ID.
    """
    stmt = select(UploadHistory.results[attribute]).where(
        UploadHistory.id == history_id
    )
    try:
        row = db.session.execute(stmt).one_or_none()
    except SQLAlchemyError as exc:
        current_app.logger.error(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD, {"history_id": history_id}
        )
        raise DatabaseError(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id}
        ) from exc

    if row is None:
        current_app.logger.error(E.UPLOAD_HISTORY_RECORD_NOT_FOUND, {"id": history_id})
        raise RecordNotFound(E.UPLOAD_HISTORY_RECORD_NOT_FOUND % {"id": history_id})

    return row[0]


def get_upload_results_with_pagination(
    history_id: UUID,
    page: int,
    size: int,
    status_filter: list[ResultStatus] | None = None,
) -> list[dict]:
    """Get paginated upload results with optional status filtering.

    Args:
        history_id (UUID): The ID of the upload history.
        page (int): The page number (1-based).
        size (int): The number of items per page.
        status_filter (list[ResultStatus]):
            Optional list of status values to filter the results.
            Following values are allowed: "create", "update", "delete", "skip", "error".

    Returns:
        list[dict]: A list of upload result items.

    Raises:
        InvalidQueryError: If page or size is less than 1.
        DatabaseError: If there is an error querying the database.
        RecordNotFound: If no history record is found for the given ID.
    """
    if page < 1 or size < 1:
        current_app.logger.error(E.INVALID_QUERY, {"page": page, "size": size})
        raise InvalidQueryError(E.INVALID_QUERY % {"page": page, "size": size})

    if not is_upload_history_exists(history_id):
        current_app.logger.error(E.UPLOAD_HISTORY_RECORD_NOT_FOUND, {"id": history_id})
        raise RecordNotFound(E.UPLOAD_HISTORY_RECORD_NOT_FOUND % {"id": history_id})

    items_element_col: TableValuedColumn[dict] = func.jsonb_array_elements(
        UploadHistory.results["items"]
    ).column_valued("item")
    stmt = (
        select(items_element_col)
        .select_from(UploadHistory)
        .where(UploadHistory.id == history_id)
    )
    if status_filter:
        stmt = stmt.where(items_element_col.op("->>")("status").in_(status_filter))

    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)

    try:
        raw_results = db.session.execute(stmt).scalars().all()
    except SQLAlchemyError as exc:
        current_app.logger.error(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD, {"history_id": history_id}
        )
        raise DatabaseError(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id}
        ) from exc
    return list(raw_results)


def create_upload(
    file_id: UUID, results: ValidateResults, operator_id: str, operator_name: str
) -> UploadHistory:
    """Create a new upload history record.

    Must call :func:`db`.session.commit() after using this function to persist changes.

    Args:
        file_id (UUID): The ID of the associated file.
        results (ValidateResults): The results of the upload operation.
        operator_id (str): The ID of the operator performing the upload.
        operator_name (str): The name of the operator performing the upload.

    Returns:
        UploadHistory: The newly created upload history record.

    Raises:
        DatabaseError:
          If there is an error creating the upload history record in the database.
    """
    results_json: _ResultData = results.model_dump(
        mode="json",
        include={"summary", "items", "missing_users"},
        exclude_none=True,
        exclude_unset=True,
        by_alias=True,
    )  # pyright: ignore[reportAssignmentType]

    history = UploadHistory()
    history.file_id = file_id
    history.results = results_json
    history.operator_id = operator_id
    history.operator_name = operator_name

    try:
        db.session.add(history)
    except SQLAlchemyError as exc:
        current_app.logger.error(
            E.FAILED_CREATE_UPLOAD_HISTORY_RECORD, {"file_id": file_id}
        )
        raise DatabaseError(
            E.FAILED_CREATE_UPLOAD_HISTORY_RECORD % {"file_id": file_id}
        ) from exc

    return history


def update_upload_status(
    history_id: UUID,
    status: t.Literal["P", "S", "F"],
    new_results: ValidateResults | None = None,
    file_id: UUID | None = None,
) -> None:
    """Update the status of an upload history record.

    Must call db.session.commit() after using this function to persist changes.

    Args:
        history_id (UUID): The ID of the history record to update.
        status (Literal["P", "S", "F"]):
          The new status ("P": Progress, "S": Success, "F": Failed).
        new_results (ValidateResults | None): New results to update, if any.
        file_id (UUID | None): New file ID to update, if any.

    Raises:
        DatabaseError: If there is an error updating the database.
    """
    try:
        obj = db.session.get(UploadHistory, history_id)
    except SQLAlchemyError as exc:
        current_app.logger.error(
            E.FAILED_UPDATE_HISTORY_RECORD_STATUS, {"history_id": history_id}
        )
        raise DatabaseError(
            E.FAILED_UPDATE_HISTORY_RECORD_STATUS % {"history_id": history_id}
        ) from exc

    if obj is None:
        return

    obj.status = status
    now = datetime.now(UTC)
    if status == "P":
        obj.timestamp = now
    else:
        obj.end_timestamp = now

    if new_results:
        obj.results = new_results.model_dump(
            mode="json",
            include={"summary", "items", "missing_users"},
            exclude_none=True,
            exclude_unset=True,
            by_alias=True,
        )  # pyright: ignore[reportAttributeAccessIssue]

    if file_id:
        obj.file_id = file_id


def get_history_by_file_id(file_id: UUID) -> UploadHistory:
    """Get a history record by its file ID.

    Args:
        file_id (UUID): The ID of the file.

    Returns:
        UploadHistory: The history record.

    Raises:
        RecordNotFound: If no history record is found for the file ID.
        DatabaseError: If there is an error querying the database.
    """
    stmt = select(UploadHistory).where(UploadHistory.file_id == file_id)
    try:
        result = db.session.execute(stmt).scalar_one_or_none()
    except SQLAlchemyError as exc:
        current_app.logger.error(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID, {"file_id": file_id}
        )
        raise DatabaseError(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID % {"file_id": file_id}
        ) from exc

    if result is None:
        current_app.logger.error(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID, {"file_id": file_id}
        )
        raise RecordNotFound(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD_BY_FILE_ID % {"file_id": file_id}
        )

    return result


def is_upload_history_exists(history_id: UUID) -> bool:
    """Check if an upload history record exists by its ID.

    Args:
        history_id (UUID): The ID of the history record.

    Returns:
        bool: True if the history record exists, False otherwise.

    Raises:
        DatabaseError: If there is an error querying the database.
    """
    stmt = select(exists().where(UploadHistory.id == history_id))
    try:
        result = db.session.execute(stmt).scalar()
    except SQLAlchemyError as exc:
        current_app.logger.error(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD, {"history_id": history_id}
        )
        raise DatabaseError(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id}
        ) from exc

    return bool(result)


def get_file_by_id(file_id: UUID) -> Files:
    """Get a file record by its ID.

    Args:
        file_id (UUID): The ID of the file to retrieve.

    Returns:
        Files: The file record.

    Raises:
        RecordNotFound: If no file record is found for the file ID.
        DatabaseError: If there is an error querying the database.
    """
    try:
        result = db.session.get(Files, file_id)
    except SQLAlchemyError as exc:
        current_app.logger.error(E.FAILED_GET_FILE_RECORD, {"file_id": file_id})
        raise DatabaseError(E.FAILED_GET_FILE_RECORD % {"file_id": file_id}) from exc

    if result is None:
        current_app.logger.error(E.FAILED_GET_FILE_RECORD, {"file_id": file_id})
        raise RecordNotFound(E.FAILED_GET_FILE_RECORD % {"file_id": file_id})

    return result


def delete_file_by_id(file_id: UUID) -> int:
    """Delete a file record by its ID.

    Must call db.session.commit() after using this function to persist changes.

    Args:
        file_id (UUID): The ID of the file to delete.

    Returns:
        int: The number of rows deleted.

    Raises:
        DatabaseError: If there is an error deleting the file from the database.
    """
    stmt = delete(Files).where(Files.id == file_id)
    try:
        result = db.session.execute(stmt)
    except SQLAlchemyError as exc:
        current_app.logger.error(E.FAILED_DELETE_FILE_RECORD, {"file_id": file_id})
        raise DatabaseError(E.FAILED_DELETE_FILE_RECORD % {"file_id": file_id}) from exc

    return t.cast("CursorResult", result).rowcount or 0


def create_file_record(
    file_path: str, file_content: FileContent, file_id: UUID | None = None
) -> Files:
    """Create a new file record in the database.

    Must call :func:`db`.session.commit() after using this function to persist changes.

    Args:
        file_path (str): The path of the file.
        file_content (FileContent): The content of the file.
        file_id (UUID | None): The ID of the file to update.

    Returns:
        Files: The created or updated file record.

    Raises:
        DatabaseError: If there is an error creating the file record in the database.
    """
    content_json: _FileContent = file_content.model_dump(  # pyright: ignore[reportAssignmentType]
        mode="json", by_alias=True, exclude_none=True
    )

    file_record = Files()
    if file_id:
        file_record.id = file_id
    file_record.file_path = str(file_path)
    file_record.file_content = content_json

    try:
        db.session.add(file_record)
    except SQLAlchemyError as exc:
        current_app.logger.error(E.FAILED_CREATE_FILE_RECORD, {"file_path": file_path})
        raise DatabaseError(
            E.FAILED_CREATE_FILE_RECORD % {"file_path": file_path}
        ) from exc

    return file_record


def create_download_history(
    file_id: UUID,
    file_path: str,
    file_content: FileContent,
    operator_id: str,
    operator_name: str,
) -> DownloadHistory:
    """Create a new download history record.

    Must call :func:`db`.session.commit() after using this function to persist changes.

    Args:
        file_id (UUID): The ID of the associated file.
        file_path (str): The path of the file.
        file_content (FileContent): The content of the file.
        operator_id (str): The ID of the operator performing the download.
        operator_name (str): The name of the operator performing the download.

    Returns:
        DownloadHistory: The newly created download history record.

    Raises:
        DatabaseError:
          If there is an error creating the download history record in the database.
    """
    create_file_record(file_path, file_content, file_id)

    download_history = DownloadHistory()
    download_history.file_id = file_id
    download_history.operator_id = operator_id
    download_history.operator_name = operator_name

    try:
        db.session.add(download_history)
    except SQLAlchemyError as exc:
        current_app.logger.error(
            E.FAILED_CREATE_DOWNLOAD_HISTORY_RECORD, {"file_id": file_id}
        )
        raise DatabaseError(
            E.FAILED_CREATE_DOWNLOAD_HISTORY_RECORD % {"file_id": file_id}
        ) from exc

    return download_history
