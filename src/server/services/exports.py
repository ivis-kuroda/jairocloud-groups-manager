#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services for managing users."""

import typing as t

from datetime import UTC, datetime
from uuid import uuid7

from server.const import (
    USER_EXPORT_HEADERS_V1,
    USER_ROLES,
)
from server.db import db
from server.entities.bulk import FileContent
from server.entities.summaries import GroupSummary, RepositorySummary, UserSummary
from server.exc import InvalidExportError
from server.messages import E
from server.services import history_table
from server.services.core import users
from server.services.utils import (
    ExportUsersCriteria,
    is_current_user_system_admin,
    make_criteria_object,
)
from server.services.utils.affiliations import detect_affiliations
from server.services.utils.permissions import get_permitted_repository_ids
from server.storage import current_storage


if t.TYPE_CHECKING:
    from pathlib import Path

    from server.entities.map_user import MapUser


def make_export_file_v1(
    operator_id: str, operator_name: str, criteria: ExportUsersCriteria | None = None
) -> Path:
    """Generate a file containing user details for the specified user IDs.

    Args:
        operator_id (str): The ID of the operator performing the export.
        operator_name (str): The name of the operator performing the export.
        criteria (ExportUsersCriteria | None):
          The export criteria containing export format and other parameters.

    Returns:
        Path: The path to the generated export file.
    """
    results = users.search(criteria or make_criteria_object("users"), raw=True)
    user_list = results.resources

    now = datetime.now(UTC)
    file_format = criteria.f if criteria and criteria.f in {"csv", "tsv"} else "tsv"
    delimiter = "," if file_format == "csv" else "\t"
    file_id = uuid7()

    target_dir: Path = current_storage / str(now.year) / str(now.month)
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / f"{file_id}.{file_format}"
    file_path.write_text(
        delimiter.join([
            "created: ",
            now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "version: ",
            "1.0",
        ])
        + "\n",
        encoding="utf-8",
    )
    file_path.write_text(
        delimiter.join(USER_EXPORT_HEADERS_V1) + "\n", encoding="utf-8"
    )

    permitted_repository_ids = get_permitted_repository_ids()

    exported_agg = _write_user_v1(
        user_list, delimiter, file_path, permitted_repository_ids
    )
    history_table.create_download_history(
        file_id, str(file_path), exported_agg, operator_id, operator_name
    )
    db.session.commit()
    return file_path


def _write_user_v1(
    user_list: list[MapUser],
    delimiter: str,
    file_path: Path,
    permitted_repository_ids: set[str],
) -> FileContent:
    """Write user details to file.

    Args:
        user_list (list[MapUser]): A list of user details.
        delimiter (str): The delimiter to use in the file.
        file_path (Path): The path to the file.
        permitted_repository_ids (list[str]): A list of permitted repository IDs.

    Returns:
        FileContent:
            A dictionary aggregating user exported.
            It has keys `repositories`, `groups`, and `users`.

    Raises:
        InvalidExportError:
          If the user cannot be exported due to insufficient permissions.
    """
    repository_agg: dict[str, RepositorySummary] = {}
    group_agg: dict[str, GroupSummary] = {}
    user_agg: dict[str, UserSummary] = {}

    is_super = is_current_user_system_admin()

    for map_user in user_list:
        roles, groups = detect_affiliations([g.value for g in map_user.groups or []])
        if not is_super and any(
            role_group.role == USER_ROLES.SYSTEM_ADMIN for role_group in roles
        ):
            raise InvalidExportError(E.USER_CANNOT_EXPORT_SYSTEM_ADMIN)

        if not is_super and not any(
            group.repository_id in permitted_repository_ids for group in groups
        ):
            raise InvalidExportError(E.USER_FORBIDDEN_EXPORT)

        user_id = t.cast("str", map_user.id)
        user_agg[user_id] = UserSummary(id=user_id, user_name=map_user.user_name or "")

        group_ids = []
        for group in groups:
            if not is_super and group.repository_id not in permitted_repository_ids:
                continue

            group_id = t.cast("str", group.group_id)
            group_agg[group_id] = GroupSummary(id=group_id)
            repository_id = t.cast("str", group.repository_id)
            repository_agg[repository_id] = RepositorySummary(id=repository_id)
            group_ids.append(group_id)

        roles_list = [
            r.role.value
            for r in roles
            if is_super or r.repository_id in permitted_repository_ids
        ] or [""]
        eppns = [eppn.value for eppn in map_user.edu_person_principal_names or []]
        emails = [email.value for email in map_user.emails or []]

        max_len = max(len(group_ids), len(roles_list), len(eppns), len(emails))

        for i in range(max_len):
            row = [
                map_user.id,
                map_user.user_name,
                group_ids[i] if i < len(group_ids) else group_ids[len(group_ids) - 1],
                "",  # group name can't be get from mAP Core API search user endpoint
                roles_list[i]
                if i < len(roles_list)
                else roles_list[len(roles_list) - 1],
                eppns[i] if i < len(eppns) else eppns[len(eppns) - 1],
                map_user.preferred_language or "",
                emails[i] if i < len(emails) else emails[len(emails) - 1],
            ]
            file_path.write_text(delimiter.join(row) + "\n", encoding="utf-8")

    return FileContent(
        repositories=list(repository_agg.values()),
        groups=list(group_agg.values()),
        users=list(user_agg.values()),
    )
