#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing history table."""

import typing as t

from datetime import UTC, datetime
from uuid import UUID  # noqa: TC003

from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from server.db import db
from server.db.history import DownloadHistory, Files, UploadHistory
from server.exc import (
    DatabaseError,
    InvalidQueryError,
    InvalidRecordError,
    RecordNotFound,
)
from server.messages import E


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
        current_app.logger.error(str(exc))
        raise DatabaseError(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id}
        ) from exc
    return history


def get_upload_results(history_id: UUID, attribute: str) -> dict:
    """Get upload results by history ID and attribute.

    Args:
        history_id (UUID): The ID of the upload history.
        attribute (str): The attribute to retrieve from results.

    Returns:
        dict: The upload results for the specified attribute.

    Raises:
        DatabaseError: If there is an error querying the database.
        RecordNotFound: If no history record is found for the given ID.
    """
    try:
        result = (
            db.session
            .query(UploadHistory.results[attribute])
            .filter(UploadHistory.id == history_id)
            .first()
        )
    except SQLAlchemyError as exc:
        current_app.logger.error(str(exc))
        raise DatabaseError(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id}
        ) from exc
    if result is None:
        current_app.logger.error(E.FAILED_GET_FILE_RECORD, {"file_id": history_id})
        raise RecordNotFound(E.FAILED_GET_FILE_RECORD % {"file_id": history_id})
    return result[0]


def get_paginated_upload_results(
    history_id: UUID, offset: int, size: int, status_filter: list[str]
) -> list[dict]:
    """Get paginated upload results with optional status filtering.

    Args:
        history_id (UUID): The ID of the upload history.
        offset (int): The page number (1-based).
        size (int): The number of items per page.
        status_filter (list[str]): List of status strings to filter results.

    Returns:
        list[dict]: A list of upload result items.

    Raises:
        InvalidQueryError: If offset or size is less than 1.
        DatabaseError: If there is an error querying the database.
    """
    if offset < 1 or size < 1:
        current_app.logger.error(E.INVALID_QUERY, {"offset": offset, "size": size})
        raise InvalidQueryError(E.INVALID_QUERY % {"offset": offset, "size": size})

    elements = func.jsonb_array_elements(
        UploadHistory.results["results"]
    ).column_valued("item")
    try:
        query = (
            db.session
            .query(elements)
            .select_from(UploadHistory)
            .filter(UploadHistory.id == history_id)
        )

        if status_filter:
            query = query.filter(elements.op("->>")("status").in_(status_filter))

        offset_val = (offset - 1) * size

        raw_results = query.limit(size).offset(offset_val).all()
    except SQLAlchemyError as exc:
        current_app.logger.error(str(exc))
        raise DatabaseError(
            E.FAILED_GET_UPLOAD_HISTORY_RECORD % {"history_id": history_id}
        ) from exc
    return [r[0] for r in raw_results]


def create_upload(
    file_id: UUID, results: dict, operator_id: str, operator_name: str
) -> UploadHistory:
    """Create a new upload history record.

    Args:
        file_id (UUID): The ID of the associated file.
        results (dict): The results of the upload operation.
        operator_id (str): The ID of the operator performing the upload.
        operator_name (str): The name of the operator performing the upload.

    Returns:
        UploadHistory: The newly created upload history record.

    Raises:
        InvalidRecordError: If the results dictionary is missing required keys.
        DatabaseError:
          If there is an error creating the upload history record in the database.
    """
    summary = results.get("summary")
    items = results.get("results")
    missing_users = results.get("missing_users", [])
    if summary is None or items is None:
        raise InvalidRecordError(E.INVALID_UPLOAD_HISTORY_RECORD_ATTRIBUTES)
    try:
        history_record = UploadHistory()
        history_record.file_id = file_id
        history_record.results = {
            "summary": summary,
            "items": items,
            "missing_users": missing_users,
        }
        history_record.operator_id = operator_id
        history_record.operator_name = operator_name
        db.session.add(history_record)
        db.session.commit()
    except SQLAlchemyError as exc:
        current_app.logger.error(str(exc))
        raise DatabaseError(
            E.FAILED_CREATE_UPLOAD_HISTORY_RECORD % {"file_id": file_id}
        ) from exc
    return history_record


def update_upload_status(
    history_id: UUID,
    status: t.Literal["P", "S", "F"],
    new_results: dict | None = None,
    file_id: UUID | None = None,
) -> None:
    """Update the status of an upload history record.

    Must call db.session.commit() after using this function to persist changes.

    Args:
        history_id (UUID): The ID of the history record to update.
        status (Literal["P", "S", "F"]):
          The new status ("P": Progress, "S": Success, "F": Failed).
        new_results (dict | None): New results to update, if any.
        file_id (UUID | None): New file ID to update, if any.

    Raises:
        DatabaseError: If there is an error updating the database.
    """
    try:
        obj = db.session.get(UploadHistory, history_id)
        if obj is None:
            return
        if new_results:
            obj.results = {
                "summary": new_results.get("summary", {}),
                "items": new_results.get("results", []),
                "missing_users": new_results.get("missing_users", []),
            }

        obj.status = status
        now = datetime.now(UTC)
        if status == "P":
            obj.timestamp = now
        else:
            obj.end_timestamp = now

        if file_id:
            obj.file_id = file_id
    except SQLAlchemyError as exc:
        current_app.logger.error(str(exc))
        raise DatabaseError(
            E.FAILED_UPDATE_HISTORY_RECORD_STATUS % {"history_id": history_id}
        ) from exc


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
    try:
        result = (
            db.session.query(UploadHistory).filter_by(file_id=file_id).one_or_none()
        )
    except SQLAlchemyError as exc:
        current_app.logger.error(str(exc))
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
        result = db.session.query(Files).filter_by(id=file_id).one_or_none()
    except SQLAlchemyError as exc:
        current_app.logger.error(str(exc))
        raise DatabaseError(E.FAILED_GET_FILE_RECORD % {"file_id": file_id}) from exc
    if result is None:
        current_app.logger.error(E.FAILED_GET_FILE_RECORD, {"file_id": file_id})
        raise RecordNotFound(E.FAILED_GET_FILE_RECORD % {"file_id": file_id})
    return result


def delete_file_by_id(file_id: UUID) -> None:
    """Delete a file record by its ID.

    Must call db.session.commit() after using this function to persist changes.

    Args:
        file_id (UUID): The ID of the file to delete.

    Raises:
        DatabaseError: If there is an error deleting the file from the database.
    """
    try:
        Files.query.filter(Files.id == file_id).delete()
    except SQLAlchemyError as exc:
        current_app.logger.error(str(exc))
        raise DatabaseError(E.FAILED_DELETE_FILE_RECORD % {"file_id": file_id}) from exc


def create_file(
    file_path: str, file_content: dict, file_id: UUID | None = None
) -> Files:
    """Create or update a file record.

    Must call db.session.commit() after using this function to persist changes.

    Args:
        file_path (str): The path of the file.
        file_content (dict): The content of the file.
        file_id (UUID | None): The ID of the file to update.

    Returns:
        Files: The created or updated file record.

    Raises:
        DatabaseError: If there is an error creating the file record in the database.
    """
    try:
        file_record = Files()
        if file_id:
            file_record.id = file_id
        file_record.file_path = str(file_path)
        file_record.file_content = {
            "repositories": file_content.get("repositories", []),
            "groups": file_content.get("groups", []),
            "users": file_content.get("users", []),
        }
        db.session.add(file_record)
    except SQLAlchemyError as exc:
        current_app.logger.error(str(exc))
        raise DatabaseError(
            E.FAILED_CREATE_FILE_RECORD % {"file_path": file_path}
        ) from exc
    return file_record


def create_download_history(
    file_id: UUID,
    file_path: str,
    file_content: dict,
    operator_id: str,
    operator_name: str,
) -> DownloadHistory:
    """Create a new download history record.

    Must call db.session.commit() after using this function to persist changes.

    Args:
        file_id (UUID): The ID of the associated file.
        file_path (str): The path of the file.
        file_content (dict): The content of the file.
        operator_id (str): The ID of the operator performing the download.
        operator_name (str): The name of the operator performing the download.

    Returns:
        DownloadHistory: The newly created download history record.

    Raises:
        DatabaseError:
          If there is an error creating the download history record in the database.
    """
    try:
        create_file(file_path, file_content, file_id)
        download_history = DownloadHistory()
        download_history.file_id = file_id
        download_history.operator_id = operator_id
        download_history.operator_name = operator_name
        db.session.add(download_history)
    except SQLAlchemyError as exc:
        current_app.logger.error(str(exc))
        raise DatabaseError(
            E.FAILED_CREATE_DOWNLOAD_HISTORY_RECORD % {"file_id": file_id}
        ) from exc
    return download_history
