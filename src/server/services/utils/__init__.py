#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides utilities for service."""

from .affiliations import detect_affiliation, detect_affiliations, detect_repository
from .decoraters import require_enabled, session_required
from .filter_options import (
    search_groups_options,
    search_history_filter_options,
    search_repositories_options,
    search_users_options,
)
from .patch_operations import build_patch_operations, build_update_member_operations
from .permissions import (
    extract_group_ids,
    filter_permitted_group_ids,
    get_current_user_affiliations,
    get_permitted_repository_ids,
    is_current_user_system_admin,
)
from .resolvers import resolve_repository_id, resolve_service_id
from .roles import get_highest_role
from .search_queries import (
    ExportUsersCriteria,
    GroupsCriteria,
    RepositoriesCriteria,
    UsersCriteria,
    build_search_query,
    make_criteria_object,
)
from .transformers import (
    prepare_group,
    prepare_role_groups,
    prepare_service,
    prepare_user,
    validate_group_to_map_group,
    validate_repository_to_map_service,
    validate_user_to_map_user,
)
