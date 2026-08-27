#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides services for managing resources in mAP Core API."""

import typing as t

from flask import current_app

from server.config import config
from server.exc import ResourceNotFound
from server.messages import E, I
from server.services import exports
from server.services.utils.search_queries import (
    ExportUsersCriteria,
    make_criteria_object,
)

from .core import groups, repositories, users


if t.TYPE_CHECKING:
    from pathlib import Path

    from server.entities.group_detail import GroupDetail
    from server.entities.map_group import MapGroup
    from server.entities.map_service import MapService
    from server.entities.map_user import MapUser
    from server.entities.repository_detail import RepositoryDetail
    from server.entities.search_request import SearchResponse, SearchResult
    from server.entities.summaries import GroupSummary, RepositorySummary, UserSummary
    from server.entities.user_detail import UserDetail
    from server.services.utils.search_queries import (
        GroupsCriteria,
        RepositoriesCriteria,
        UsersCriteria,
    )


class RepositoryService:
    """Service class for managing Repositories."""

    @t.overload
    @staticmethod
    def search(criteria: RepositoriesCriteria) -> SearchResult[RepositorySummary]: ...
    @t.overload
    @staticmethod
    def search(
        criteria: RepositoriesCriteria, *, raw: t.Literal[True]
    ) -> SearchResponse[MapService]: ...
    @staticmethod
    def search(
        criteria: RepositoriesCriteria, *, raw: bool = False
    ) -> SearchResult[RepositorySummary] | SearchResponse[MapService]:
        """Search for repositories based on given criteria.

        Args:
            criteria (RepositoriesCriteria): Search criteria for filtering repositories.
            raw (bool):
                If True, return raw search response from mAP Core API.
                Defaults to False.

        Returns:
            Search results. The type depends on the `raw` argument.
            - SearchResult[RepositorySummary]:
                Search result containing Repository summaries. It has members `total`,
                `page_size`, `offset`, and `resources`.
            - SearchResponse[MapService]:
                Raw search response from mAP Core API, if `raw` is True.
                It has members `schemas`,`total_results`, `start_index`,
                `items_per_page`, and `resources`.

        """
        return repositories.search(criteria, raw=raw)  # pyright: ignore[reportArgumentType]

    @t.overload
    @staticmethod
    def get_by_id(
        repository_id: str, *, more_detail: bool = False
    ) -> RepositoryDetail | None: ...
    @t.overload
    @staticmethod
    def get_by_id(repository_id: str, *, raw: t.Literal[True]) -> MapService | None: ...
    @staticmethod
    def get_by_id(
        repository_id: str, *, raw: bool = False, more_detail: bool = False
    ) -> RepositoryDetail | MapService | None:
        """Get a Repository by its ID.

        Args:
            repository_id (str): ID of the Repository.
            more_detail (bool):
                If True, include more details such as groups and users count.
            raw (bool): If True, return raw MapService object. Defaults to False.

        Returns:
            The Repository if found, otherwise None. The type depends on the `raw`
            argument.
            - RepositoryDetail: The Repository detail object.
            - MapService: The raw Repository object from mAP Core API.
        """
        return repositories.get_by_id(repository_id, raw=raw, more_detail=more_detail)  # pyright: ignore[reportCallIssue]

    @staticmethod
    def create(repository: RepositoryDetail) -> RepositoryDetail:
        """Create a new Repository.

        Args:
            repository (RepositoryDetail): The Repository to create.

        Returns:
            RepositoryDetail: The created Repository.
        """
        admins = UserService.get_system_admins()

        groups.create_role_groups(
            t.cast("str", repository.id), t.cast("str", repository.service_name), admins
        )
        return repositories.create(repository, admins)

    @staticmethod
    def update(repository: RepositoryDetail) -> RepositoryDetail:
        """Update an existing Repository.

        Args:
            repository (RepositoryDetail):
                The Repository data to update. The `id` field is required.

        Returns:
            RepositoryDetail: The updated Repository.
        """
        if config.MAP_CORE.update_strategy == "put":
            return repositories.update_put(repository)

        return repositories.update(repository)

    @staticmethod
    def delete_by_id(repository_id: str, service_name: str) -> RepositoryDetail:
        """Delete a Repository.

        Args:
            repository_id (str): ID of the Repository to delete.
            service_name (str):
                Name of the service associated with the Repository resource to confirm.

        Returns:
            RepositoryDetail: The deleted Repository.
        """
        deleted = repositories.delete_by_id(repository_id, service_name)
        groups_to_delete = [*(deleted._groups or []), *(deleted._rolegroups or [])]  # ruff:ignore[private-member-access]
        groups.delete_multiple(set(groups_to_delete))

        return deleted


class GroupService:
    """Service class for managing Groups."""

    @t.overload
    @staticmethod
    def search(criteria: GroupsCriteria) -> SearchResult[GroupSummary]: ...
    @t.overload
    @staticmethod
    def search(
        criteria: GroupsCriteria, *, raw: t.Literal[True]
    ) -> SearchResponse[MapGroup]: ...
    @staticmethod
    def search(
        criteria: GroupsCriteria, *, raw: bool = False
    ) -> SearchResult[GroupSummary] | SearchResponse[MapGroup]:
        """Search for groups based on given criteria.

        Args:
            criteria (GroupsCriteria): Search criteria for filtering groups.
            raw (bool):
                If True, return raw search response from mAP Core API.
                Defaults to False.

        Returns:
            Search results. The type depends on the `raw` argument.
            - SearchResult[GroupSummary]:
                Search result containing Group summaries. It has members `total`,
                `page_size`, `offset`, and `resources`.
            - SearchResponse[MapGroup]:
                Raw search response from mAP Core API, if `raw` is True.
                It has members `schemas`, `total_results`, `start_index`,
                `items_per_page`, and `resources`.
        """
        return groups.search(criteria, raw=raw)  # pyright: ignore[reportArgumentType]

    @t.overload
    @staticmethod
    def get_by_id(
        group_id: str, *, more_detail: bool = False
    ) -> GroupDetail | None: ...
    @t.overload
    @staticmethod
    def get_by_id(group_id: str, *, raw: t.Literal[True]) -> MapGroup | None: ...
    @staticmethod
    def get_by_id(
        group_id: str, *, raw: bool = False, more_detail: bool = False
    ) -> GroupDetail | MapGroup | None:
        """Get a Group by its ID.

        Args:
            group_id (str): ID of the Group.
            more_detail (bool):
                If True, include more details such as users count.
            raw (bool): If True, return raw MapGroup object. Defaults to False.

        Returns:
            The Group if found, otherwise None. The type depends on the `raw`
            argument.
            - GroupDetail: The Group detail object.
            - MapGroup: The raw Group object from mAP Core API.
        """
        return groups.get_by_id(group_id, raw=raw, more_detail=more_detail)  # pyright: ignore[reportCallIssue]

    @staticmethod
    def create(group: GroupDetail) -> GroupDetail:
        """Create a new Group.

        Args:
            group (GroupDetail): The Group to create.

        Returns:
            GroupDetail: The created Group.
        """
        admins = UserService.get_system_admins()
        return groups.create(group, admins)

    @staticmethod
    def update(group: GroupDetail) -> GroupDetail:
        """Update group from mAP Core API by group_id.

        Args:
            group (GroupDetail): The Group data to update. The `id` field is required.

        Returns:
            GroupDetail: The updated Group detail object.
        """
        if config.MAP_CORE.update_strategy == "put":
            return groups.update_put(group)

        return groups.update(group)

    @staticmethod
    def update_members(
        group_id: str, add: set[str] | None = None, remove: set[str] | None = None
    ) -> GroupDetail:
        """Update group members by group ID in mAP Core API .

        Args:
            group_id (str): ID of the Group resource.
            add (set[str]): Set of user IDs to add.
            remove (set[str]): Set of user IDs to remove.

        Returns:
            GroupDetail: updated group detail
        """
        admins = UserService.get_system_admins()
        if config.MAP_CORE.update_strategy == "put":
            return groups.update_member_put(group_id, add, remove, system_admins=admins)

        return groups.update_members(group_id, add, remove, system_admins=admins)

    @staticmethod
    def delete_multiple(group_ids: set[str]) -> set[str] | None:
        """Delete groups from mAP Core API by group_ids.

        Args:
            group_ids (set[str]): ID of the Group resource.

        Returns:
            set[str]: group id list of failed.
        """
        if not config.FEATURES.enable_bulk_operation:
            return groups.delete_multiple_sequentially(group_ids)

        return groups.delete_multiple(group_ids)

    @staticmethod
    def delete_by_id(group_id: str) -> GroupDetail:
        """Delete a Group.

        Args:
            group_id (str): ID of the Group to delete.

        Returns:
            GroupDetail: The deleted Group.
        """
        return groups.delete_by_id(group_id)


class UserService:
    """Service class for managing Users."""

    @t.overload
    @staticmethod
    def search(criteria: UsersCriteria) -> SearchResult[UserSummary]: ...
    @t.overload
    @staticmethod
    def search(
        criteria: UsersCriteria, *, raw: t.Literal[True]
    ) -> SearchResponse[MapUser]: ...
    @staticmethod
    def search(
        criteria: UsersCriteria, *, raw: bool = False
    ) -> SearchResult[UserSummary] | SearchResponse[MapUser]:
        """Search for users based on given criteria.

        Args:
            criteria (UsersCriteria): Search criteria for filtering users.
            raw (bool):
                If True, return raw search response from mAP Core API.
                Defaults to False.

        Returns:
            object: Search results. The type depends on the `raw` argument.
            - SearchResult;
                Search result containing User summaries. It has members `total`,
                `page_size`, `offset`, and `resources`.
            - SearchResponse;
                Raw search response from mAP Core API. It has members `schemas`,
                `total_results`, `start_index`, `items_per_page`, and `resources`.
        """
        return users.search(criteria, raw=raw)  # pyright: ignore[reportArgumentType]

    @staticmethod
    def count(criteria: UsersCriteria) -> int:
        """Count users based on given criteria.

        Args:
            criteria (UsersCriteria): Search criteria for filtering users.

        Returns:
            int: The total number of users matching the criteria.
        """
        criteria.l = 0
        return users.search(criteria, raw=True).total_results

    @t.overload
    @staticmethod
    def get_by_id(user_id: str, *, more_detail: bool = False) -> UserDetail | None: ...
    @t.overload
    @staticmethod
    def get_by_id(user_id: str, *, raw: t.Literal[True]) -> MapUser | None: ...
    @staticmethod
    def get_by_id(
        user_id: str, *, raw: bool = False, more_detail: bool = False
    ) -> UserDetail | MapUser | None:
        """Get a User by its ID.

        Args:
            user_id (str): ID of the User.
            more_detail (bool):
                If True, include more details such as groups and repositories count.
            raw (bool): If True, return raw MapUser object. Defaults to False.

        Returns:
            The User if found, otherwise None. The type depends on the `raw`
            argument.
            - UserDetail: The User detail object.
            - MapUser: The raw User object from mAP Core API.
        """
        return users.get_by_id(user_id, raw=raw, more_detail=more_detail)  # pyright: ignore[reportCallIssue]

    @t.overload
    @staticmethod
    def get_by_eppn(eppn: str, *, more_detail: bool = False) -> UserDetail | None: ...
    @t.overload
    @staticmethod
    def get_by_eppn(eppn: str, *, raw: t.Literal[True]) -> MapUser | None: ...
    @staticmethod
    def get_by_eppn(
        eppn: str, *, raw: bool = False, more_detail: bool = False
    ) -> UserDetail | MapUser | None:
        """Get a User by its EPPN.

        Args:
            eppn (str): EPPN of the User.
            more_detail (bool):
                If True, include more details such as groups and repositories count.
            raw (bool): If True, return raw MapUser object. Defaults to False.

        Returns:
            The User if found, otherwise None. The type depends on the `raw`
            argument.
            - UserDetail: The User detail object.
            - MapUser: The raw User object from mAP Core API.
        """
        return users.get_by_eppn(eppn, raw=raw, more_detail=more_detail)  # pyright: ignore[reportCallIssue]

    @staticmethod
    def create(user: UserDetail) -> UserDetail:
        """Create a new User.

        Args:
            user (UserDetail): The User to create.

        Returns:
            UserDetail: The created User.
        """
        return users.create(user)

    @classmethod
    def update(cls, user: UserDetail) -> UserDetail:
        """Update an existing User.

        Args:
            user (UserDetail): The User data to update. The `id` field is required.

        Returns:
            UserDetail: The updated User.
        """
        if not config.MAP_CORE.user_editable:
            return cls.update_affiliations(user)

        if config.MAP_CORE.update_strategy == "put":
            return users.update_put(user)

        return users.update(user)

    @classmethod
    def update_affiliations(cls, user: UserDetail) -> UserDetail:
        """Update affiliations of an existing User.

        Args:
            user (UserDetail): The User data to update. The `id` field is required.

        Returns:
            UserDetail: The updated User.

        Raises:
            ResourceNotFound: If the User with the given ID does not exist.
        """
        if (current := cls.get_by_id(user_id := t.cast("str", user.id))) is None:
            current_app.logger.error(E.FAILED_UPDATE_USER, {"id": user_id})
            raise ResourceNotFound(E.USER_NOT_FOUND % {"id": user_id})

        return NotImplemented

    @t.overload
    @classmethod
    def get_system_admins(cls) -> set[str]: ...
    @t.overload
    @classmethod
    def get_system_admins(cls, *, raw: t.Literal[True]) -> list[MapUser]: ...
    @classmethod
    def get_system_admins(cls, *, raw: bool = False) -> set[str] | list[MapUser]:
        """Get system administrators.

        Args:
            raw (bool): If True, return raw MapUser objects. Defaults to False.

        Returns:
            list: The list of system administrators. The type of items depends on
                the `raw` argument.
            - str: The IDs of the system administrators.
            - MapUser: The raw User objects of system administrators from mAP Core API.
        """
        criteria = make_criteria_object("users", a=[0], super=True)
        try:
            result = cls.search(criteria, raw=True)
        finally:
            current_app.logger.info(I.SEARCHED_SYSTEM_ADMINS)

        if raw:
            return result.resources

        return {t.cast("str", user.id) for user in result.resources}

    @staticmethod
    def make_export_file(
        operator_id: str,
        operator_name: str,
        criteria: ExportUsersCriteria | None = None,
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
        match config.USERS.export_format_version:
            case 1.0:
                return exports.make_export_file_v1(operator_id, operator_name, criteria)
            case _:
                return NotImplemented  # pragma: no cover
