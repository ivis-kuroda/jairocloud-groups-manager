#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Services to provide resource transformers for entities."""

# ruff: noqa: SLF001

import typing as t

from flask import current_app

from server.config import config
from server.const import (
    GROUP_DEFAULT_MEMBER_LIST_VISIBILITY,
    GROUP_DEFAULT_PUBLIC,
    USER_ROLES,
)
from server.entities.group_detail import (
    GroupDetail,
    Repository as GroupRepository,
)
from server.entities.map_group import (
    Administrator as GroupAdministrator,
    MapGroup,
    MemberUser,
    Service as GroupService,
)
from server.entities.map_service import (
    Administrator as ServiceAdministrator,
    Group as MapServiceGroup,
    MapService,
    ServiceEntityID,
)
from server.entities.map_user import EPPN, Email, Group as UserGroup, MapUser
from server.entities.repository_detail import RepositoryDetail
from server.entities.summaries import GroupSummary
from server.entities.user_detail import RepositoryRole, UserDetail
from server.exc import InvalidFormError, SystemAdminNotFound
from server.messages import E

from .affiliations import detect_affiliation, detect_affiliations
from .permissions import (
    get_permitted_repository_ids,
    is_current_user_system_admin as is_super,
)
from .resolvers import resolve_repository_id, resolve_service_id
from .search_queries import make_criteria_object


def prepare_service(
    repository: RepositoryDetail, administrators: set[str]
) -> tuple[MapService, str]:
    """Prepare MapService instance from RepositoryDetail to create.

    Args:
        repository (RepositoryDetail): The repository detail to be converted.
        administrators (set[str]): The set of administrator user IDs.

    Returns:
        tuple: Converted MapService instance and repository ID.

    Raises:
        SystemAdminNotFound: If no administrators are provided.
    """
    service = validate_repository_to_map_service(repository)
    repository_id = t.cast("str", repository.id)

    if not administrators:
        error = E.REPOSITORY_REQUIRES_SYSTEM_ADMIN
        raise SystemAdminNotFound(error)

    service.administrators = [
        ServiceAdministrator(value=user_id) for user_id in administrators
    ]
    service.groups = [
        MapServiceGroup(
            value=config.GROUPS.id_patterns[role].format(repository_id=repository_id)
        )
        for role in USER_ROLES
    ]
    return service, repository_id


def prepare_role_groups(
    repository_id: str, service_name: str, administrators: set[str]
) -> list[MapGroup]:
    """Prepare role groups for a repository creation.

    Args:
        repository_id (str): The ID of the repository.
        service_name (str): The name of the service.
        administrators (set[str]): The set of administrator user IDs.

    Returns:
        list[MapGroup]: A list of MapGroup instances representing the role groups.

    Raises:
        SystemAdminNotFound: If no administrators are provided.
    """
    service_id = resolve_service_id(repository_id=repository_id)

    if not administrators:
        error = E.REPOSITORY_REQUIRES_SYSTEM_ADMIN
        raise SystemAdminNotFound(error)

    role_groups = []
    for role in USER_ROLES:
        if role == USER_ROLES.SYSTEM_ADMIN:
            continue  # System admin group is not necessary.

        id_pattern = config.GROUPS.id_patterns[role]
        name_pattern = config.GROUPS.name_patterns[role]
        role_groups.append(
            MapGroup(
                id=id_pattern.format(repository_id=repository_id),
                display_name=name_pattern.format(repository_name=service_name),
                public=GROUP_DEFAULT_PUBLIC,
                member_list_visibility=GROUP_DEFAULT_MEMBER_LIST_VISIBILITY,
                administrators=[
                    GroupAdministrator(value=user_id) for user_id in administrators
                ],
                services=[
                    GroupService(value=config.SP.connector_id),
                    GroupService(value=service_id),
                ],
            )
        )
    return role_groups


def make_repository_detail(
    service: MapService, *, more_detail: bool = False
) -> RepositoryDetail:
    """Convert a MapService instance to a RepositoryDetail instance.

    Args:
        service (MapService): The MapService instance to convert.
        more_detail (bool): Whether to include more details such as groups and users.

    Returns:
        RepositoryDetail: The converted RepositoryDetail instance.
    """
    repository_id = resolve_repository_id(service_id=service.id)

    entity_ids = None
    if service.entity_ids:
        entity_ids = [eid.value for eid in service.entity_ids]

    repository = RepositoryDetail(
        id=repository_id,
        service_id=service.id,
        service_name=service.service_name,
        service_url=service.service_url,
        active=not service.suspended if service.suspended is not None else None,
        entity_ids=entity_ids,
    )

    if not more_detail or not service.groups:
        return repository

    from server.services import users  # noqa: PLC0415

    valid_groups = [
        (g.value, detected)
        for g in service.groups
        if (detected := detect_affiliation(g.value)) is not None
    ]
    detected_rolegroups = [i for i, g in valid_groups if g.type == "role"]
    detected_groups = [i for i, g in valid_groups if g.type == "group"]

    groups_count = len(detected_groups)
    users_count = users.count(make_criteria_object("users", g=detected_groups))

    repository.groups_count = groups_count
    repository.users_count = users_count
    repository.created = service.meta.created if service.meta else None
    repository._groups = detected_groups
    repository._rolegroups = detected_rolegroups
    repository._admins = (
        [admin.value for admin in service.administrators]
        if service.administrators
        else None
    )

    return repository


def validate_repository_to_map_service(repository: RepositoryDetail) -> MapService:
    """Validate the RepositoryDetail instance and convert it to a MapService instance.

    Args:
        repository (RepositoryDetail): The RepositoryDetail instance to convert.

    Returns:
        MapService: The converted MapService instance.

    Raises:
        InvalidFormError:  If the repository cannot be converted to a MapService.
    """
    repository_id = repository.id
    service_url = repository.service_url

    if repository.service_name is None:
        error = E.REPOSITORY_REQUIRES_SERVICE_NAME
        raise InvalidFormError(error)

    if service_url is None:
        error = E.REPOSITORY_REQUIRES_SERVICE_URL
        raise InvalidFormError(error)

    if repository_id is None:
        fqdn = service_url.host
        repository_id = resolve_repository_id(fqdn=fqdn) if fqdn else None

    if repository_id is None:
        error = E.REPOSITORY_INVALID_SERVICE_URL
        raise InvalidFormError(error)

    max_url_length = config.REPOSITORIES.max_url_length
    without_scheme_url = str(service_url).replace(f"{service_url.scheme}://", "")
    if len(without_scheme_url) > max_url_length:
        error = E.REPOSITORY_TOO_LONG_URL % {"max": max_url_length}
        raise InvalidFormError(error)

    if not repository.entity_ids:
        error = E.REPOSITORY_REQUIRES_ENTITY_ID
        raise InvalidFormError(error)

    repository.id = repository_id  # Ensure the repository ID is set for later use.
    repository.service_id = resolve_service_id(repository_id=repository_id)
    return make_map_service(repository)


def make_map_service(repository: RepositoryDetail) -> MapService:
    """Convert a RepositoryDetail instance to a MapService instance.

    Args:
        repository (RepositoryDetail): The RepositoryDetail instance to convert.

    Returns:
        MapService: The converted MapService instance.
    """
    service_id = repository.service_id or resolve_service_id(
        repository_id=t.cast("str", repository.id)
    )
    service = MapService(
        id=service_id,
        service_name=repository.service_name,
        service_url=repository.service_url,
    )
    if repository.active is not None:
        service.suspended = repository.active is False
    if repository.entity_ids:
        service.entity_ids = [
            ServiceEntityID(value=eid) for eid in repository.entity_ids
        ]
    return service


def prepare_group(
    detail: GroupDetail,
    administrators: set[str],
) -> MapGroup:
    """Prepare a MapGroup instance from a GroupDetail instance.

    Args:
        detail (GroupDetail): The GroupDetail instance to convert.
        administrators (set[str]): The set of administrator user IDs.

    Returns:
        MapGroup: The converted MapGroup instance.

    Raises:
        SystemAdminNotFound: If no administrators are found.
    """
    map_group, repository_id = validate_group_to_map_group(detail, mode="create")
    service_id = resolve_service_id(repository_id=repository_id)

    if not administrators:
        error = E.GROUP_REQUIRES_SYSTEM_ADMIN
        raise SystemAdminNotFound(error)

    map_group.administrators = [
        GroupAdministrator(value=user_id) for user_id in administrators
    ]
    map_group.services = [
        GroupService(value=config.SP.connector_id),
        GroupService(value=service_id),
    ]

    return map_group


def make_group_detail(group: MapGroup, *, more_detail: bool = False) -> GroupDetail:
    """Convert a MapGroup instance to a GroupDetail instance.

    Args:
        group (MapGroup): The MapGroup instance to convert.
        more_detail (bool): Whether to include more detailed information.

    Returns:
        GroupDetail: The created GroupDetail instance.
    """
    detected = detect_affiliation(group.id or "")

    detail = GroupDetail(
        id=group.id,
        display_name=group.display_name,
        description=group.description,
        public=group.public,
        member_list_visibility=group.member_list_visibility,
        type=detected.type if detected else None,
    )

    if group.members:
        users = [member for member in group.members if member.type == "User"]
        user_count = len(users)
        detail.users_count = user_count
        detail._users = [member.value for member in users]

    if group.administrators:
        detail._admins = [admin.value for admin in group.administrators]

    if group.services:
        detail._services = [service.value for service in group.services]

    if group.meta:
        detail.created = group.meta.created
        detail.last_modified = group.meta.last_modified

    if not more_detail:
        return detail

    detected = detect_affiliation(t.cast("str", group.id))
    repository_id = detected.repository_id if detected else None
    detail.user_defined_id = (
        detected.user_defined_id if detected and detected.type == "group" else None
    )
    repository_id = detected.repository_id if detected else None
    if repository_id:
        from server.services import repositories  # noqa: PLC0415

        if repo := repositories.get_by_id(repository_id):
            detail.repository = GroupRepository(
                id=repository_id, service_name=repo.service_name
            )

    return detail


@t.overload
def validate_group_to_map_group(
    group: GroupDetail, *, mode: t.Literal["create"]
) -> tuple[MapGroup, str]: ...
@t.overload
def validate_group_to_map_group(
    group: GroupDetail, *, mode: t.Literal["update"]
) -> MapGroup: ...


def validate_group_to_map_group(  # noqa: C901
    group: GroupDetail, *, mode: t.Literal["create", "update"]
) -> tuple[MapGroup, str] | MapGroup:
    """Validate the GroupDetail instance and convert it to a MapGroup instance.

    Args:
        group (GroupDetail): The GroupDetail instance to convert.
        mode (Literal["create", "update"]):
            The mode of operation, either "create" or "update".

    Returns:
        tuple: The converted MapGroup instance and the repository ID associated with it.

    Raises:
        InvalidFormError: If the GroupDetail instance cannot be converted to a MapGroup.
    """
    if not group.display_name:
        error = E.GROUP_REQUIRES_DISPLAY_NAME
        raise InvalidFormError(error)

    if mode == "update":
        if not group.id:
            error = E.GROUP_REQUIRES_ID
            raise InvalidFormError(error)

        detected = detect_affiliation(group.id)
        current_app.logger.error("Detected affiliation: %s", detected)
        if not detected:
            # out of this service's scope.
            error = E.GROUP_INVALID_ID_PATTERN
            raise InvalidFormError(error)

        if detected.repository_id:
            # ensure the repository detected.
            group.repository = GroupRepository(id=detected.repository_id)

        return make_map_group(group)

    repository_id = group.repository.id if group.repository else None
    if not repository_id:
        error = E.GROUP_REQUIRES_REPOSITORY
        raise InvalidFormError(error)

    from server.services import repositories  # noqa: PLC0415

    if repositories.get_by_id(repository_id) is None:
        error = E.GROUP_REQUIRES_EXISTING_REPOSITORY % {"rid": repository_id}
        raise InvalidFormError(error)

    if not is_super() and repository_id not in get_permitted_repository_ids():
        error = E.GROUP_FORBIDDEN_REPOSITORY % {"rid": repository_id}
        raise InvalidFormError(error)

    user_defined_id = group.user_defined_id
    if not user_defined_id:
        error = E.GROUP_REQUIRES_USER_DEFINED_ID
        raise InvalidFormError(error)

    max_id_length = config.GROUPS.max_id_length - len(repository_id)
    if len(user_defined_id) > max_id_length:
        error = E.GROUP_TOO_LONG_ID % {"rid": repository_id, "max": max_id_length}
        raise InvalidFormError(error)

    id_pattern = config.GROUPS.id_patterns.user_defined
    group.id = id_pattern.format(
        repository_id=repository_id, user_defined_id=user_defined_id
    )

    if group.public is None:
        group.public = GROUP_DEFAULT_PUBLIC
    if group.member_list_visibility is None:
        group.member_list_visibility = GROUP_DEFAULT_MEMBER_LIST_VISIBILITY

    return make_map_group(group), repository_id


def make_map_group(group: GroupDetail) -> MapGroup:
    """Convert a GroupDetail instance to a MapGroup instance.

    Args:
        group (GroupDetail): The GroupDetail instance to convert.

    Returns:
        MapGroup: The converted MapGroup instance.
    """
    map_group = MapGroup(
        id=group.id,
        display_name=group.display_name,
        public=group.public,
        description=group.description,
        member_list_visibility=group.member_list_visibility,
    )

    if group._users:
        map_group.members = [MemberUser(type="User", value=uid) for uid in group._users]

    if group._admins:
        map_group.administrators = [
            GroupAdministrator(value=uid) for uid in group._admins
        ]

    if group._services:
        map_group.services = [GroupService(value=sid) for sid in group._services]

    return map_group


def prepare_user(user: UserDetail) -> MapUser:
    """Prepare a MapUser instance from a UserDetail instance.

    Args:
        user (UserDetail): The UserDetail instance to convert.

    Returns:
        MapUser: The converted MapUser instance.
    """
    return validate_user_to_map_user(user, mode="create")


def make_user_detail(user: MapUser, *, more_detail: bool = False) -> UserDetail:
    """Convert a MapUser instance to a UserDetail instance.

    Args:
        user (MapUser): The MapUser instance to convert.
        more_detail (bool):
            Whether to include more details such as groups and repositories.

    Returns:
        UserDetail: The converted UserDetail instance.
    """
    detail = UserDetail(
        id=user.id,
        user_name=user.user_name or "",
        preferred_language=user.preferred_language or None,
    )

    if user.edu_person_principal_names:
        detail.eppns = [eppn.value for eppn in user.edu_person_principal_names]

    if user.emails:
        detail.emails = [email.value for email in user.emails]

    if user.meta:
        detail.created = user.meta.created
        detail.last_modified = user.meta.last_modified

    if not user.groups:
        return detail

    permitted = get_permitted_repository_ids()
    detected_repos, detected_groups = detect_affiliations([
        group.value for group in user.groups
    ])
    group_ids = {
        g.group_id
        for g in detected_groups
        if is_super() or g.repository_id in permitted
    }
    user_roles = {
        role.repository_id: role.role
        for role in detected_repos
        if role.repository_id
        if is_super() or role.repository_id in permitted
    }

    is_system_admin = any(
        role.role == USER_ROLES.SYSTEM_ADMIN for role in detected_repos
    )
    if is_system_admin:
        # System Administrator did not affiliate with any repository
        detail.is_system_admin = is_system_admin and is_super()

        return detail

    if not more_detail:
        detail.groups = [GroupSummary(id=gid) for gid in group_ids]
        detail.repository_roles = [
            RepositoryRole(id=repository_id, user_role=role)
            for repository_id, role in user_roles.items()
        ]
        return detail

    if group_ids:
        from server.services import groups  # noqa: PLC0415

        group_query = make_criteria_object("groups", i=list(group_ids), l=-1)
        detail.groups = [
            g
            for g in groups.search(criteria=group_query).resources
            if g.id in group_ids
        ]

    if user_roles:
        from server.services import repositories  # noqa: PLC0415

        repositories_query = make_criteria_object(
            "repositories", i=list(user_roles.keys()), l=-1
        )
        detail.repository_roles = [
            RepositoryRole(
                id=r.id,
                service_name=r.service_name,
                user_role=user_roles[r.id],
            )
            for r in repositories.search(criteria=repositories_query).resources
            if r.id in user_roles
        ]

    return detail


def validate_user_to_map_user(
    user: UserDetail, *, mode: t.Literal["create", "update"]
) -> MapUser:
    """Validate the UserDetail instance and convert it to a MapUser instance.

    Args:
        user (UserDetail): The UserDetail instance to convert.
        mode (Literal["create", "update"]):
            The mode of operation, either "create" or "update".

    Returns:
        MapUser: The converted MapUser instance.

    Raises:
        InvalidFormError: If the UserDetail instance cannot be converted to a MapUser.
    """
    if mode == "create":
        if not user.user_name:
            error = E.USER_REQUIRES_USERNAME
            raise InvalidFormError(error)

        if not user.eppns or all(not _ for _ in user.eppns):
            error = E.USER_REQUIRES_EPPN
            raise InvalidFormError(error)

        if not user.emails or all(not _ for _ in user.emails):
            error = E.USER_REQUIRES_EMAIL
            raise InvalidFormError(error)

        if user.is_system_admin and not is_super():
            error = E.USER_NO_CREATE_SYSTEM_ADMIN
            raise InvalidFormError(error)

    if user.is_system_admin:
        if not is_super():
            error = E.USER_NO_PROMOTE_SYSTEM_ADMIN
            raise InvalidFormError(error)

        if user.repository_roles:
            error = E.USER_REQUIRES_NO_REPOSITORY
            raise InvalidFormError(error)

        if user.groups:
            error = E.USER_REQUIRES_NO_GROUP
            raise InvalidFormError(error)

        user.groups = [GroupSummary(id=config.GROUPS.id_patterns.system_admin)]
        return make_map_user(user)

    permitted = get_permitted_repository_ids()

    valid_group_ids = validate_user_roles(user, permitted)
    valid_group_ids.extend(validate_user_groups(user, permitted))

    user.groups = [GroupSummary(id=gid) for gid in valid_group_ids]
    return make_map_user(user)


def validate_user_roles(user: UserDetail, permitted: set[str]) -> list[str]:
    """Validate the repository roles of a UserDetail instance.

    Args:
        user (UserDetail): The UserDetail instance to validate.
        permitted (set[str]): The set of permitted repository IDs for the user.

    Returns:
        list[str]: A list of valid group IDs based on the user's repository roles.

    Raises:
        InvalidFormError:
            If the user specifies non-existent or non-permitted repositories.
    """
    if not user.repository_roles or all(
        not _.id or not _.user_role for _ in user.repository_roles
    ):
        error = E.USER_REQUIRES_REPOSITORY
        raise InvalidFormError(error)

    from server.services import repositories  # noqa: PLC0415

    repositories_query = make_criteria_object(
        "repositories",
        i=[role.id for role in user.repository_roles if role.id],
        l=-1,
    )
    existed = {r.id for r in repositories.search(criteria=repositories_query).resources}

    valid_group_ids: list[str] = []
    for repo_role in user.repository_roles:
        if not (rid := repo_role.id):
            continue

        if rid not in existed:
            error = E.USER_REQUIRES_EXISTING_REPOSITORY % {"id": rid}
            raise InvalidFormError(error)

        if not is_super() and repo_role.id not in permitted:
            error = E.USER_FORBIDDEN_REPOSITORY % {"id": repo_role.id}
            raise InvalidFormError(error)

        user_role = repo_role.user_role
        if not user_role or user_role == USER_ROLES.SYSTEM_ADMIN:
            continue

        pattern = config.GROUPS.id_patterns[user_role]
        valid_group_ids.append(pattern.format(repository_id=repo_role.id))

    return valid_group_ids


def validate_user_groups(user: UserDetail, permitted: set[str]) -> list[str]:
    """Validate the groups of a UserDetail instance.

    Args:
        user (UserDetail): The UserDetail instance to validate.
        permitted (set): The set of permitted repository IDs for the user.

    Returns:
        list: A list of valid group IDs based on the user's groups.

    Raises:
        InvalidFormError:
            If the user specifies non-existent or non-permitted groups.
    """
    if not user.groups:
        return []

    specified = [group.id for group in user.groups if group.id]
    current_app.logger.error("Specified group IDs: %s", specified)
    _, detected = detect_affiliations(specified)
    group_query = make_criteria_object(
        "groups", i=[group.group_id for group in detected], l=-1
    )

    from server.services import groups  # noqa: PLC0415

    existed = {g.id for g in groups.search(criteria=group_query).resources}
    current_app.logger.error("Existed group IDs: %s", existed)

    if non_existent := set(specified) - existed:
        error = E.USER_REQUIRES_EXISTING_GROUP % {"id": ", ".join(non_existent)}
        raise InvalidFormError(error)

    for group in detected:
        if is_super() or group.repository_id in permitted:
            continue

        error = E.USER_FORBIDDEN_GROUP % {"id": group.group_id}
        raise InvalidFormError(error)

    return [group.group_id for group in detected]


def make_map_user(user: UserDetail) -> MapUser:
    """Convert a UserDetail instance to a MapUser instance.

    Args:
        user (UserDetail): The UserDetail instance to convert.

    Returns:
        MapUser: The converted MapUser instance.
    """
    map_user = MapUser(
        id=user.id,
        user_name=user.user_name,
        preferred_language=user.preferred_language or None,
    )

    if user.eppns:
        map_user.edu_person_principal_names = [
            EPPN(value=eppn) for eppn in user.eppns if eppn.strip()
        ]

    if user.emails:
        map_user.emails = [Email(value=email) for email in user.emails if email.strip()]

    groups: list[UserGroup] = []

    if user.groups:
        groups.extend(
            UserGroup(value=group.id) for group in user.groups if group.id.strip()
        )

    if user.is_system_admin:
        pattern = config.GROUPS.id_patterns.system_admin
        groups.append(UserGroup(value=pattern))

    if user.repository_roles:
        groups.extend(
            UserGroup(
                value=config.GROUPS.id_patterns[role].format(
                    repository_id=repository.id
                )
            )
            for repository in user.repository_roles
            if (role := repository.user_role) and role != USER_ROLES.SYSTEM_ADMIN
        )

    if groups:
        map_user.groups = groups

    return map_user
