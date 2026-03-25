#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Provides signals for services in the application."""

from blinker import Namespace


repository_signals = Namespace()
"""Namespace for signals related to repository operations."""

repository_created = repository_signals.signal("created")
repository_updated = repository_signals.signal("updated")
repository_deleted = repository_signals.signal("deleted")


group_signals = Namespace()
"""Namespace for signals related to group operations."""

group_created = group_signals.signal("created")
group_updated = group_signals.signal("updated")
group_deleted = group_signals.signal("deleted")


user_signals = Namespace()
"""Namespace for signals related to user operations."""

user_created = user_signals.signal("created")
user_updated = user_signals.signal("updated")
user_deleted = user_signals.signal("deleted")
user_promoted = user_signals.signal("promoted")
user_demoted = user_signals.signal("demoted")
