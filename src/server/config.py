#
# Copyright (C) 2025 National Institute of Informatics.
#

"""Configuration for the server application.

Provides validation, loading, and global access to runtime configuration.
"""

# ruff: noqa: S105, N802

import ast
import operator
import re
import typing as t

from datetime import timedelta

from flask import current_app
from pydantic import (
    AnyUrl,
    BaseModel,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from sqlalchemy.engine import URL
from weko_group_cache_db.config import (
    Sentinel as CacheDbSentinel,
    Settings as CacheDbSettings,
)
from werkzeug.local import LocalProxy

from server.const import (
    HAS_REPO_ID_AND_USER_DEFINED_ID_PATTERN,
    HAS_REPO_ID_PATTERN,
    HAS_REPO_NAME_PATTERN,
    USER_ROLES,
)
from server.messages import E


if t.TYPE_CHECKING:
    from collections import abc

    from server.ext import JAIROCloudGroupsManager


class RuntimeConfig(BaseSettings):
    """Schema for runtime configuration.

    Handles validation and loading of runtime config values.
    """

    SERVER_NAME: str = "localhost"
    """Server hostname of this application."""

    SECRET_KEY: str = "CHANGE ME"
    """Secret key for cryptographic operations."""

    LOG: LogConfig
    """Logging configuration."""

    SESSION: SessionConfig = Field(
        default_factory=lambda: SessionConfig(),  # noqa: PLW0108
    )
    """Session configuration."""

    API: ApiConfig = Field(
        default_factory=lambda: ApiConfig(),  # noqa: PLW0108
    )
    """API configuration."""

    STORAGE: StorageConfig = Field(
        default_factory=lambda: StorageConfig(),  # noqa: PLW0108
    )
    """Storage configuration."""

    MAP_CORE: MapCoreConfig
    """mAP Core service configuration."""

    SP: SpConfig
    """This application's Service Provider configuration."""

    REPOSITORIES: RepositoriesConfig
    """Repository related configuration values."""

    GROUPS: GroupsConfig
    """Group related configuration values."""

    USERS: UsersConfig
    """Users related configuration values."""

    POSTGRES: PostgresConfig = Field(
        default_factory=lambda: PostgresConfig(),  # noqa: PLW0108
        exclude=True,
    )
    """PostgreSQL database configuration values."""

    REDIS: RedisConfig
    """Redis cache configuration values."""

    RABBITMQ: RabbitmqConfig
    """RabbitMQ configuration values."""

    CACHE_GROUPS: CacheGroupsConfig
    """Cache groups task configuration values."""

    FEATURES: FeaturesConfig
    """Feature flags for enabling/disabling application features.

    These are due to temporary constraints
    in the future, all features will be enabled and the settings will be deleted.
    """

    DEVELOP: DevelopConfig | None = None

    @computed_field
    @property
    def for_group_caches(self) -> CacheDbSettings:
        """Cache database configuration values."""
        endpoint = (
            self.MAP_CORE.base_url.rstrip("/")
            + "/"
            + self.CACHE_GROUPS.api_endpoint.lstrip("/")
        )

        return self.CACHE_GROUPS.model_copy(
            update={
                "LOG_LEVEL": self.LOG.level,
                "SP_CONNECTOR_ID_PREFIX": self.SP.connector_id,
                "MAP_GROUPS_API_ENDPOINT": endpoint,
                "REDIS_TYPE": self.REDIS.cache_type,
                "REDIS_HOST": self.REDIS.single.base_url.host,
                "REDIS_PORT": self.REDIS.single.base_url.port,
                "REDIS_DB_INDEX": self.REDIS.database.group_cache,
                "REDIS_SENTINEL_MASTER": self.REDIS.sentinel.master_name,
                "SENTINELS": [
                    CacheDbSentinel(host=node.host, port=node.port)
                    for node in self.REDIS.sentinel.nodes
                ],
            }
        )

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> URL:
        """Database connection URI for SQLAlchemy."""
        pg = self.POSTGRES
        return URL.create(
            "postgresql+psycopg", pg.user, pg.password, pg.host, pg.port, pg.db
        )

    @computed_field
    @property
    def CELERY(self) -> dict[str, t.Any]:
        """Celery configuration dictionary.

        Returns:
            dict: Configuration dictionary for Celery.
        """
        cache_type = self.REDIS.cache_type
        database = self.REDIS.database.result_backend
        config: dict[str, t.Any] = {"broker_url": str(self.RABBITMQ.url)}

        if cache_type == "RedisCache" and self.REDIS.single:
            base_url = self.REDIS.single.base_url
            config["result_backend"] = f"{base_url}/{database}"

        elif cache_type == "RedisSentinelCache" and self.REDIS.sentinel:
            sentinels = [
                f"sentinel://{node.host}:{node.port}"
                for node in self.REDIS.sentinel.nodes
            ]
            master_name = self.REDIS.sentinel.master_name
            config["result_backend"] = f"{';'.join(sentinels)}/{database}"
            config["result_backend_transport_options"] = {"master_name": master_name}

        return config

    @computed_field
    @property
    def PERMANENT_SESSION_LIFETIME(self) -> timedelta:
        """Duration (in seconds) for permanent sessions."""
        return timedelta(seconds=self.SESSION.absolute_lifetime)

    @computed_field
    @property
    def REMEMBER_COOKIE_DURATION(self) -> timedelta:
        """Duration (in seconds) for 'remember me' cookies."""
        match self.SESSION.strategy:
            case "absolute":
                lifetime = timedelta(seconds=self.SESSION.absolute_lifetime)
            case "sliding":
                lifetime = timedelta(seconds=self.SESSION.sliding_lifetime)

        return lifetime

    @computed_field
    @property
    def REMEMBER_COOKIE_REFRESH_EACH_REQUEST(self) -> bool:
        """Whether to refresh 'remember me' cookies on each request."""
        return self.SESSION.strategy == "sliding"

    @property
    def FLASK(self) -> dict[str, t.Any]:
        """Configuration dictionary suitable for Flask app.config.

        Returns:
            dict: Configuration dictionary for Flask.
        """
        return self.model_dump(
            include={
                "SERVER_NAME",
                "SECRET_KEY",
                "CELERY",
                "PERMANENT_SESSION_LIFETIME",
                "REMEMBER_COOKIE_DURATION",
                "REMEMBER_COOKIE_REFRESH_EACH_REQUEST",
            }
        ) | {
            "SQLALCHEMY_DATABASE_URI": self.SQLALCHEMY_DATABASE_URI,
            "PREFERRED_URL_SCHEME": "https",
            "SESSION_COOKIE_SECURE": True,
            "SESSION_COOKIE_SAMESITE": "Lax",
        }

    @t.override
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        origin = super().settings_customise_sources(
            settings_cls,
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

        toml_file: str | None = init_settings().pop("_toml_file", None)
        if toml_file is None:
            return origin

        toml_settings = TomlConfigSettingsSource(cls, toml_file)
        return (*origin, toml_settings)

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        alias_generator=lambda s: s.lower(),
        validate_default=True,
        validate_by_name=True,
    )
    """Base model configuration."""


class LogConfig(BaseModel):
    """Schema for logging configuration."""

    level: t.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    """Log level for the application standard output."""

    format: str | None = None
    """Log format string for log messages.
    If not provided, default formats will be used.
    """

    datefmt: str | None = None
    """Date format string for log timestamps.
    If not provided, the default format will be used.
    """


class SessionConfig(BaseModel):
    """Schema for session configuration."""

    strategy: t.Literal["absolute", "sliding"] = "sliding"
    """Strategy for session expiration."""

    sliding_lifetime: t.Annotated[int, "seconds"] = 1 * 60 * 60
    """Sliding session lifetime (in seconds)."""

    absolute_lifetime: t.Annotated[int, "seconds"] = 24 * 60 * 60
    """Absolute session lifetime (in seconds)."""


class ApiConfig(BaseModel):
    """Schema for API configuration."""

    max_upload_size: t.Annotated[int, "bytes"] = 10 * 1024**2
    """Maximum allowed file upload size (in bytes)."""


class StorageConfig(BaseModel):
    """Schema for storage configuration."""

    type: t.Literal["local"] = "local"
    """Type of storage backend to use."""

    local: LocalStorageConfig = Field(
        default_factory=lambda: LocalStorageConfig(),  # noqa: PLW0108
    )
    """Configuration for local storage backend."""


class LocalStorageConfig(BaseModel):
    """Schema for local storage configuration."""

    temporary: str = "/var/tmp/jcgroups"  # noqa: S108
    """Path to the temporary directory."""

    storage: str = "/var/tmp/jcgroups"  # noqa: S108
    """Path to the storage directory."""


class SpConfig(BaseModel):
    """Schema for Service Provider configuration."""

    connector_id: str
    """SP Connecter ID for this application."""

    entity_id: str
    """Entity ID of the Service Provider."""

    crt: str
    """Path to the Service Provider's certificate file."""

    key: str
    """Path to the Service Provider's private key file."""


class RepositoriesConfig(BaseModel):
    """Schema for repository related configuration."""

    id_patterns: RepositoriesIdPatternsConfig
    """Patterns for repository-related IDs."""

    max_url_length: t.Annotated[int, "expression"] = 50
    """Maximum allowed length for repository URL, expressed as a Python expression."""

    @field_validator("max_url_length", mode="before")
    @classmethod
    def validate_max_url_length(cls, value: str) -> int:
        """Validate and evaluate the max_url_length expression.

        Args:
            value (str): The expression to evaluate for max_url_length.

        Returns:
            int|str: The evaluated max_url_length value.

        Raises:
            ValueError: If the expression is invalid or does not evaluate to an integer.
        """
        try:
            pursed = safe_eval(value)
        except (SyntaxError, TypeError) as exc:
            error = E.INVALID_EXPRESSION
            raise ValueError(error) from exc
        return t.cast("int", pursed)


class RepositoriesIdPatternsConfig(BaseModel):
    """Schema for repository-related ID patterns."""

    sp_connector: HasRepoId
    """SP Connector ID pattern. It should include one `{repository_id}` placeholder."""


class GroupsConfig(BaseModel):
    """Schema for Group resource ID configuration."""

    id_patterns: GroupIdPatternsConfig
    """Patterns for Group resource IDs."""

    name_patterns: GroupNamePatternsConfig
    """Patterns for Group resource names."""

    max_id_length: t.Annotated[int, "expression"] = 50
    """Maximum allowed length for group ID, expressed as a Python expression."""

    @field_validator("max_id_length", mode="before")
    @classmethod
    def validate_max_id_length(cls, value: str) -> int:
        """Validate and evaluate the max_id_length expression.

        Args:
            value (str): The expression to evaluate for max_id_length.

        Returns:
            int: The evaluated max_id_length value.

        Raises:
            ValueError: If the expression is invalid or does not evaluate to an integer.
        """
        try:
            pursed = safe_eval(value)
        except (SyntaxError, TypeError) as exc:
            error = E.INVALID_EXPRESSION
            raise ValueError(error) from exc
        return t.cast("int", pursed)


class GroupIdPatternsConfig(BaseModel):
    """Schema for Group resource ID patterns."""

    system_admin: str
    """ID of the system administrator group."""

    repository_admin: HasRepoId
    """Pattern for repository administrator group IDs."""

    community_admin: HasRepoId
    """Pattern for community administrator group IDs."""

    contributor: HasRepoId
    """Pattern for contributor group IDs."""

    general_user: HasRepoId
    """Pattern for general user group IDs."""

    user_defined: HasRepoAndUserDefinedId
    """Pattern for user-defined group IDs."""

    def __getitem__(self, key: USER_ROLES | t.Literal["user_defined"]) -> str:  # noqa: D105
        return getattr(self, key)


class GroupNamePatternsConfig(BaseModel):
    """Schema for Group resource name patterns."""

    system_admin: str
    """Name of the system administrator group."""

    repository_admin: HasRepoName
    """Name pattern for repository administrator groups."""

    community_admin: HasRepoName
    """Name pattern for community administrator groups."""

    contributor: HasRepoName
    """Name pattern for contributor groups."""

    general_user: HasRepoName
    """Name pattern for general user groups."""

    def __getitem__(self, key: USER_ROLES) -> str:  # noqa: D105
        return getattr(self, key)


class UsersConfig(BaseModel):
    """Schema for user export file configuration."""

    export_format_version: float = 1.0
    """Version of the export file format."""


class MapCoreConfig(BaseModel):
    """Schema for mAP Core service configuration."""

    base_url: str
    """Base URL of the mAP Core service."""

    timeout: t.Annotated[int, "seconds"] = 10
    """Timeout (in seconds) for requests to mAP Core service."""

    update_strategy: t.Literal["put", "patch"] = "patch"
    """Update strategy for mAP Core service."""

    user_editable: bool = True
    """Whether the user information is editable via this application."""


class PostgresConfig(BaseModel):
    """Schema for PostgreSQL database configuration."""

    user: str = "jcgroups"
    """Database user name for authentication."""

    password: str = "jcpass"
    """Database user password for authentication."""

    host: str = "localhost"
    """Host name or IP address of the PostgreSQL server."""

    port: int = 5432
    """Port number for the PostgreSQL server."""

    db: str = "jcgroups"
    """Name of the PostgreSQL database."""


class RedisConfig(BaseModel):
    """Schema for Redis cache configuration."""

    cache_type: t.Literal["RedisCache", "RedisSentinelCache"] = "RedisCache"
    """Type of cache backend to use.

    Possible values are 'RedisCache' and 'RedisSentinelCache'.
    """

    socket_timeout: float = 1.0
    """Socket timeout (in seconds) for Redis connections."""

    cache_timeout: t.Annotated[int, "seconds"] = 300
    """Default timeout (in seconds) for cached items."""

    key_prefix: str = "jcgroups-"
    """Prefix for cache keys used by the application."""

    database: RedisDatabaseConfig = Field(
        default_factory=lambda: RedisDatabaseConfig(),  # noqa: PLW0108
    )

    single: RedisSingleConfig = Field(
        default_factory=lambda: RedisSingleConfig(),  # noqa: PLW0108
    )
    """Configuration for single Redis server, when cache_type is "RedisCache"."""

    sentinel: RedisSentinelCacheConfig = Field(
        default_factory=lambda: RedisSentinelCacheConfig(),  # noqa: PLW0108
    )
    """Configuration for Redis Sentinel, when cache_type is "RedisSentinelCache"."""


class RedisDatabaseConfig(BaseModel):
    """Schema for Redis database configuration."""

    app_cache: int = 0
    """Database number for application cache."""

    account_store: int = 1
    """Database number for storing account information."""

    result_backend: int = 2
    """Database number for Celery result backend."""

    group_cache: int = 4
    """Database number for group informations cache.

    refer to https://github.com/RCOSDP/weko-group-cache-db
    """


class RedisSingleConfig(BaseModel):
    """Schema for single Redis server configuration."""

    base_url: AnyUrl = AnyUrl("redis://localhost:6379")


class RedisSentinelCacheConfig(BaseModel):
    """Schema for Redis Sentinel configuration."""

    master_name: str = "mymaster"
    """Name of the Redis Sentinel master node."""

    nodes: list[SentinelNodeConfig] = Field(default_factory=list)


class SentinelNodeConfig(BaseModel):
    """Schema for Redis Sentinel node configuration."""

    host: str
    """Hostname or IP address of the Sentinel node."""

    port: int
    """Port number of the Sentinel node."""


class RabbitmqConfig(BaseModel):
    """Schema for RabbitMQ configuration."""

    url: AnyUrl = AnyUrl("amqp://guest:guest@localhost:5672//")
    """Hostname or IP address of the RabbitMQ server for Celery broker."""


class CacheGroupsConfig(CacheDbSettings):
    """Schema for cache groups configuration."""

    api_endpoint: str
    """Map groups API endpoint."""

    directory_path: str
    """Path to the directory containing institution TLS files."""


type HasRepoId = t.Annotated[
    str, StringConstraints(pattern=re.compile(HAS_REPO_ID_PATTERN))
]
"""String with a pattern for role-based group IDs.

It should include one `{repository_id}` placeholder.
"""

type HasRepoName = t.Annotated[
    str, StringConstraints(pattern=re.compile(HAS_REPO_NAME_PATTERN))
]
"""String with a pattern for role-based group names.

It should include one `{repository_name}` placeholder.
"""


type HasRepoAndUserDefinedId = t.Annotated[
    str, StringConstraints(pattern=re.compile(HAS_REPO_ID_AND_USER_DEFINED_ID_PATTERN))
]
"""String with a pattern for user-defined group IDs.

It should include one `{repository_id}`, followed by one `{user_defined_id}`
placeholders.
"""


class FeaturesConfig(BaseModel):
    """Schema for feature flags configuration."""

    search_only_username: bool = True
    """Whether user search by user name only in users.
    If false, Enable search by username, email, or ePPN.
    """

    enable_bulk_operation: bool = False
    """Whether mAP Core API bulk operation is enabled or disabled."""


type Features = t.Literal["search_only_username", "enable_bulk_operation"]


class DevelopConfig(BaseModel):
    """Schema for development environment configuration."""

    developer_login: bool = False
    """Whether to enable developer login in development mode."""

    accounts: list[DevAccountConfig] = Field(default_factory=list)
    """List of development accounts."""


class DevAccountConfig(BaseModel):
    """Schema for development account configuration."""

    id: str
    """mAP Core ID of the development account."""

    eppn: str
    """EPPN of the development account."""

    is_member_of: str
    """isMemberOf attribute of the development account."""

    user_name: str
    """User name of the development account."""


def safe_eval(expr: str) -> object:
    """Safely evaluate a restricted arithmetic expression.

    Supported:
        - int / float literals
        - str literals (for len)
        - +, -, *, /
        - len, max, min

    Args:
        expr (str): The expression to evaluate.

    Returns:
        int|str: The result of the evaluated expression.
    """
    ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.FloorDiv: operator.floordiv,
    }

    def _eval(node: ast.AST) -> object:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.BinOp) and (op := type(node.op)) in ops:
            return ops[op](_eval(node.left), _eval(node.right))

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [_eval(a) for a in node.args]
            if node.func.id == "len":
                # if args[0] is not Sized, it will raise a TypeError.
                return len(t.cast("abc.Sized", args[0]))
            if node.func.id == "max":
                # if args are not comparable, it will raise a TypeError.
                return max(args)  # pyright: ignore[reportArgumentType]
            if node.func.id == "min":
                # if args are not comparable, it will raise a TypeError.
                return min(args)  # pyright: ignore[reportArgumentType]

        raise ValueError(E.UNSUPPORTED_EXPRESSION % {"exp": expr})

    return _eval(ast.parse(expr, mode="eval").body)


# Rebuild models to resolve aliased imports.
CacheGroupsConfig.model_rebuild(_types_namespace={"Sentinel": CacheDbSentinel})
RuntimeConfig.model_rebuild(_types_namespace={"Sentinel": CacheDbSentinel})


def load_config(toml_path: str) -> RuntimeConfig:
    """Load and initialize the runtime configuration.

    Args:
        toml_path (str): Path to the TOML config file.

    Returns:
        RuntimeConfig: The initialized config instance.

    """
    return RuntimeConfig(_toml_file=toml_path)  # pyright: ignore[reportCallIssue]


def __get_config() -> RuntimeConfig:
    ext: JAIROCloudGroupsManager = current_app.extensions["jairocloud-groups-manager"]
    return ext.config


def _config():  # noqa: ANN202, for intersection-type inference
    def __type_assertion(_: object) -> t.TypeIs[RuntimeConfig]:
        return True

    proxy = LocalProxy(lambda: __get_config())  # noqa: PLW0108

    if not __type_assertion(proxy):
        raise NotImplementedError  # pragma: no cover

    return proxy


config = _config()
"""Proxy for global :class:`RuntimeConfig` instance."""
