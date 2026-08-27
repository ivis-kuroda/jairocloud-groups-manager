#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides utilities for service."""

from .affiliations import (
    detect_affiliated_repository,
    detect_affiliation,
    detect_affiliations,
    detect_affiliations_from_is_member_of,
    parse_affiliated_group_ids,
)
from .decorators import require_enabled, session_required
from .filter_options import (
    search_groups_options,
    search_history_filter_options,
    search_repositories_options,
    search_users_options,
)
from .patch_operations import build_patch_operations, build_update_member_operations
from .permissions import (
    filter_permitted_group_ids,
    get_permitted_repository_ids,
    is_current_user_system_admin,
)
from .resolvers import resolve_repository_id, resolve_service_id
from .roles import get_highest_role
from .search_queries import (
    ExportUsersCriteria,
    GroupsCriteria,
    HistoryCriteria,
    OperatorsCriteria,
    RepositoriesCriteria,
    UsersCriteria,
    build_search_query,
    make_criteria_object,
)
from .transformers import (
    make_group_detail,
    make_group_summary,
    make_map_group,
    make_map_service,
    make_map_user,
    make_repository_detail,
    make_repository_summary,
    make_user_detail,
    make_user_summary,
    prepare_group,
    prepare_role_groups,
    prepare_service,
    prepare_user,
    validate_group_to_map_group,
    validate_repository_to_map_service,
    validate_user_to_map_user,
)
