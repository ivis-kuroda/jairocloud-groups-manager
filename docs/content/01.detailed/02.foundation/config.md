---
title: config
description: サーバー設定値の管理機能を提供する。
---

## RuntimeConfig
サーバー設定値を管理するクラス。  
運用上適切な値を設定することを想定したサーバ設定値を外部から読み込む機能を提供する。
安全な設定値の一元管理と、プロパティによる動的生成を担う。  

#### シグネチャ
```python[config.py]
class RuntimeConfig(BaseSettings):
```

#### 依存するライブラリ
- **Pydantic / pydantic-settings**： 設定値の型安全管理・読み込みに使用。
- **SQLAlchemy**： データベース接続 URI の型にこのライブラリの型を使用。

#### 継承元
`pydantic_settings.BaseSettings`

#### クラス属性

| 名前         | 型                                        | 説明                  |
| ------------ | ----------------------------------------- | --------------------- |
| SERVER_NAME  | str                                       | サーバ名              |
| SECRET_KEY   | str                                       | 暗号化用キー          |
| LOG          | [LogConfig](#logconfig)                   | ログ設定              |
| SESSION      | [SessionConfig](#sessionconfig)           | セッション管理設定    |
| API          | [ApiConfig](#apiconfig)                   | API 設定              |
| STORAGE      | [StorageConfig](#storageconfig)           | ストレージ設定        |
| SP           | [SpConfig](#spconfig)                     | SP 設定               |
| MAP_CORE     | [MapCoreConfig](#mapcoreconfig)           | mAP Core サービス設定 |
| REPOSITORIES | [RepositoriesConfig](#repositoriesconfig) | リポジトリ設定        |
| GROUPS       | [GroupsConfig](#groupsconfig)             | グループ設定          |
| POSTGRES     | [PostgresConfig](#postgresconfig)         | Postgres 設定         |
| REDIS        | [RedisConfig](#redisconfig)               | Redis 設定            |
| RABBITMQ     | [RabbitmqConfig](#rabbitmqconfig)         | RabbitMQ 設定         |

#### 算出プロパティ  
これらは `@computed_field`{lang=python} デコレータを使用し、他の属性値から算出される値で属性としてアクセスされる。  

| プロパティ名                         | 型                    | 説明                                                  |
| ------------------------------------ | --------------------- | ----------------------------------------------------- |
| CELERY                               | dict[str, Any]        | Celery 拡張の設定値                                   |
| SQLALCHEMY_DATABASE_URI              | sqlalchemy.engine.URL | SQLAlchemy 拡張のデータベース接続 URI                 |
| PERMANENT_SESSION_LIFETIME           | timedelta             | Flask セッションの有効期限                            |
| REMEMBER_COOKIE_DURATION             | timedelta             | Flask-Login の remember me クッキーの有効期限         |
| REMEMBER_COOKIE_REFRESH_EACH_REQUEST | bool                  | Flask-Login の remember me クッキーのリフレッシュ設定 |

#### プロパティ

| プロパティ名 | 型   | 説明                                     |
| ------------ | ---- | ---------------------------------------- |
| for_flask    | dict | Flask アプリケーションに登録する設定値群 |

#### メソッド

| 名前                         | 型    | 説明                                   |
| ---------------------------- | ----- | -------------------------------------- |
| settings_customise_sources() | tuple | 設定値の読み込み順序を制御するメソッド |

#### 注釈
- すべての属性はサーバー設定値のトップレベルのキーに対応していて、snake_case および UPPER_SNAKE_CASE で読み込み可能である。

### CELERY
Celery 拡張の設定値を提供するプロパティ。
Redis および RabbitMQ の設定値をもとに、ブローカーやバックエンドの URL などを含む設定値を生成する。

#### シグネチャ
```python[config.py]
@computed_field
@property
def CELERY(self) -> dict[str, Any]:
```

#### デコレータ
- `@computed_field`{lang=python}： Pydantic の算出フィールドを定義するデコレータ。
- `@property`{lang=python}： プロパティを定義するデコレータ。

#### 処理内容
1. 属性 `REDIS` から Redis の接続構成に合わせた URL を生成し、`result_backend` とする。
   接続構成が Redis Sentinel である場合は、マスターノードの名前を `result_backend_transport_options` に含める。
2. 属性 `RABBITMQ` から RabbitMQ の URL を取得し、`broker_url` とする。
3. 上記を含む辞書を生成し、戻り値として返す。

### SQLALCHEMY_DATABASE_URI
Postgres 設定値をもとにデータベースの URI を提供するプロパティ。
Flask-SQLAlchemy はこの値を使用してデータベース接続を行う。

#### シグネチャ
```python[config.py]
@computed_field
@property
def SQLALCHEMY_DATABASE_URI(self) -> sqlalchemy.engine.URL:
```

#### デコレータ
- `@computed_field`{lang=python}： Pydantic の算出フィールドを定義するデコレータ。
- `@property`{lang=python}： プロパティを定義するデコレータ。

#### 処理内容
1. 属性 `POSTGRES` の各値を使用して、 SQLAlchemy のデータベース接続 URI を生成する。
   スキーマは `postgresql+psycopg` を使用する。
2. 生成したデータベース接続 URI を返す。

### PERMANENT_SESSION_LIFETIME
セッションの有効期限を提供するプロパティ。Flask のセッション管理で使用される。

#### シグネチャ
```python[config.py]
@computed_field
@property
def PERMANENT_SESSION_LIFETIME(self) -> timedelta:
```

#### デコレータ
- `@computed_field`{lang=python}： Pydantic の算出フィールドを定義するデコレータ。
- `@property`{lang=python}： プロパティを定義するデコレータ。

#### 処理内容
1. 属性 `SESSION` の絶対有効期限を `timedelta` に変換し、戻り値として返す。

### REMEMBER_COOKIE_DURATION
Flask-Login の remember me クッキーの有効期限を提供するプロパティ。

#### シグネチャ
```python[config.py]
@computed_field
@property
def REMEMBER_COOKIE_DURATION(self) -> timedelta:
```

#### デコレータ
- `@computed_field`{lang=python}： Pydantic の算出フィールドを定義するデコレータ。
- `@property`{lang=python}： プロパティを定義するデコレータ。

#### 処理内容
1. 属性 `SESSION` の セッションの期限の戦略に応じて、スライディング有効期限もしくは絶対有効期限を `timedelta` に変換し、戻り値として返す。

### REMEMBER_COOKIE_REFRESH_EACH_REQUEST
Flask-Login の remember me クッキーのリフレッシュ設定を提供するプロパティ。

#### シグネチャ
```python[config.py]
@computed_field
@property
def REMEMBER_COOKIE_REFRESH_EACH_REQUEST(self) -> bool:
```

#### デコレータ
- `@computed_field`{lang=python}： Pydantic の算出フィールドを定義するデコレータ。
- `@property`{lang=python}： プロパティを定義するデコレータ。

#### 処理内容
1. 属性 `SESSION` の セッションの期限の戦略に応じて、スライディングセッションであれば `True`{lang=python} を、絶対セッションであれば `False`{lang=python} を戻り値として返す。

### for_flask
Flask アプリケーションに登録する設定値群を提供するプロパティ。

#### シグネチャ
```python[config.py]
@property
def for_flask(self) -> dict[str, t.Any]:
```

#### デコレータ
- `@property`{lang=python}： プロパティを定義するデコレータ。

#### 処理内容
1. Flask アプリケーションに登録する設定値を辞書形式で生成し、戻り値として返す。  
   以下の設定値と追加の設定値を含む。
    - `SERVER_NAME`
    - `SECRET_KEY`
    - `CELERY`
    - `SQLALCHEMY_DATABASE_URI`
    - `PERMANENT_SESSION_LIFETIME`
    - `REMEMBER_COOKIE_DURATION`
    - `REMEMBER_COOKIE_REFRESH_EACH_REQUEST`
    - `SESSION_COOKIE_SECURE`（常に `True`{lang=python} を設定する）
    - `SESSION_COOKIE_SAMESITE`（常に `"Lax"` を設定する）
  

### settings_customise_sources
設定値の読み込みを制御するメソッド。  
標準で提供される設定ソースに加え、 TOML ファイルからの読み込みを追加する。
戻り値のタプルに含まれる順序で設定ソースが適用される。

#### シグネチャ
```python[config.py]
@override
@classmethod
def settings_customise_sources(
    cls, settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource
) -> tuple[PydanticBaseSettingsSource, ...]:
```

#### デコレータ
- `@override`{lang=python}： メソッドがスーパークラスのメソッドをオーバーライドしていることを示すデコレータ。
- `@classmethod`{lang=python}： クラスメソッドを定義するデコレータ。

#### 引数

| 名前                 | 型                         | 説明                                    |
| -------------------- | -------------------------- | --------------------------------------- |
| settings_cls         | type\[BaseSettings\]       | 設定クラスの型                          |
| init_settings        | PydanticBaseSettingsSource | コンストラクタ引数からの設定ソース      |
| env_settings         | PydanticBaseSettingsSource | 環境変数からの設定ソース                |
| dotenv_settings      | PydanticBaseSettingsSource | .env ファイルからの設定ソース           |
| file_secret_settings | PydanticBaseSettingsSource | Kubernetes シークレットからの設定ソース |

#### 戻り値
| 型                                       | 説明                             |
| ---------------------------------------- | -------------------------------- |
| tuple\[PydanticBaseSettingsSource, ...\] | カスタムされた設定ソースのタプル |

#### 処理内容
1. 継承元クラスの `settings_customise_sources` メソッドを呼び出し、標準の設定ソースタプルを取得する。
2. 引数 `init_settings` から `_toml_file` キーを取り出し、 TOML ファイルのパスを取得する。
3. TOML ファイルのパスが存在しない場合、標準の設定ソースタプルをそのまま戻り値として返す。  
   存在する場合、設定ソースタプルの末尾に TOML ファイルのパスで初期化した `pydantic_settings.TomlSettingsSource` を追加し、戻り値として返す。


## LogConfig
アプリケーションログに関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class LogConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前    | 型                                                        | 説明             |
| ------- | --------------------------------------------------------- | ---------------- |
| level   | Literal\["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | ログレベル       |
| format  | str                                                       | ログフォーマット |
| datefmt | str                                                       | 日付フォーマット |


## SessionConfig
セッション管理に関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class SessionConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前              | 型                               | 説明                                   |
| ----------------- | -------------------------------- | -------------------------------------- |
| strategy          | Literal\["absolute", "sliding"\] | セッションの有効期限の戦略             |
| sliding_lifetime  | int                              | スライディングセッション有効期限（秒） |
| absolute_lifetime | int                              | 絶対セッション有効期限（秒）           |


## ApiConfig
API に関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class ApiConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前            | 型  | 説明                             |
| --------------- | --- | -------------------------------- |
| max_upload_size | int | アップロードサイズ上限（バイト） |


## StorageConfig
ストレージに関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class StorageConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前  | 型                                  | 説明                   |
| ----- | ----------------------------------- | ---------------------- |
| type  | Literal\["local", "ObjectStorage"\] | ストレージの種類       |
| local | LocalStorageConfig                  | ローカルストレージ設定 |

#### 備考
オブジェクトストレージの設定は現状サポートしていない。


## LocalStorageConfig
ローカルストレージに関するサーバー設定値を管理するクラス。 [`StorageConfig`](#storageconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class LocalStorageConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

| 名前      | 型  | 説明                                   |
| --------- | --- | -------------------------------------- |
| temporary | str | 一時ファイルの保存先ディレクトリのパス |
| storage   | str | 永続ファイルの保存先ディレクトリのパス |


## SpConfig
当システムの SP に関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class SpConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前         | 型  | 説明               |
| ------------ | --- | ------------------ |
| connector_id | str | SP コネクタの ID   |
| entity_id    | str | SP エンティティ ID |
| crt          | str | SP 証明書パス      |
| key          | str | SP 秘密鍵パス      |


## MapCoreConfig
mAP Core サービスに関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class MapCoreConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前            | 型                        | 説明                                         |
| --------------- | ------------------------- | -------------------------------------------- |
| base_url        | str                       | mAP Core サービスの URL                      |
| timeout         | int                       | リクエストタイムアウト秒数                   |
| update_strategy | Literal\["put", "patch"\] | リソース更新の HTTP メソッド                 |
| user_editable   | bool                      | 当システムによって User リソースが更新可能か |

#### 備考
- `update_strategy` は mAP Core API V2 の User リソースの更新に使用される HTTP メソッドを指定する。
  現支店では mAP Core API V2 が PATCH メソッドに対応していない。
- mAP Core API V2 の User リソースの更新は、ユーザー自身のみの権限をもつアクセストークンが要求される。
  `user_editable` が `False`{lang=python} の場合、当システムは User リソースの更新を行わず、 Group リソースを更新することでユーザーの所属グループの管理を行う。


## RepositoriesConfig
リポジトリに関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class RepositoriesConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前           | 型                                                        | 説明                       |
| -------------- | --------------------------------------------------------- | -------------------------- |
| id_patterns    | [RepositoryIdPatternsConfig](#repositoryidpatternsconfig) | リポジトリ ID パターン設定 |
| max_url_length | int                                                       | リポジトリ URL 長の上限    |

#### 備考
- `max_url_length` は整数に評価可能な式を文字列で指定されることを想定している。
  四則演算と組み込み関数 `max` 、 `min` 、 `len` のみが使用可能である。


## RepositoryIdPatternsConfig
リポジトリ ID パターンに関するサーバー設定値を管理するクラス。 [`RepositoriesConfig`](#repositoriesconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class RepositoryIdPatternsConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前         | 型                      | 説明                      |
| ------------ | ----------------------- | ------------------------- |
| sp_connector | [HasRepoId](#hasrepoid) | SP コネクタ ID のパターン |


## GroupsConfig
グループに関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class GroupsConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前          | 型                                                  | 説明                     |
| ------------- | --------------------------------------------------- | ------------------------ |
| id_patterns   | [GroupIdPatternsConfig](#groupidpatternsconfig)     | グループ ID パターン設定 |
| name_patterns | [GroupNamePatternsConfig](#groupnamepatternsconfig) | グループ名パターン設定   |
| max_id_length | int                                                 | グループ ID 長の上限     |

#### 備考
- `max_id_length` は整数に評価可能な式を文字列で指定されることを想定している。
  四則演算と組み込み関数 `max` 、 `min` 、 `len` のみが使用可能である。


## GroupIdPatternsConfig
グループ ID パターンに関するサーバー設定値を管理するクラス。 [`GroupsConfig`](#groupsconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class GroupIdPatternsConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前             | 型                                                  | 説明                                     |
| ---------------- | --------------------------------------------------- | ---------------------------------------- |
| system_admin     | [HasRepoId](#hasrepoid)                             | システム管理者グループ ID のパターン     |
| repository_admin | [HasRepoId](#hasrepoid)                             | リポジトリ管理者グループ ID のパターン   |
| community_admin  | [HasRepoId](#hasrepoid)                             | コミュニティ管理者グループ ID のパターン |
| contributor      | [HasRepoId](#hasrepoid)                             | 投稿ユーザーグループ ID のパターン       |
| general_user     | [HasRepoId](#hasrepoid)                             | 一般ユーザーグループ ID のパターン       |
| user_defined     | [HasRepoAndUserDefinedId](#hasrepoanduserdefinedid) | ユーザー定義グループ ID のパターンリスト |


## GroupNamePatternsConfig
グループ名パターンに関するサーバー設定値を管理するクラス。 [`GroupsConfig`](#groupsconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class GroupNamePatternsConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前             | 型                          | 説明                                   |
| ---------------- | --------------------------- | -------------------------------------- |
| system_admin     | [HasRepoName](#hasreponame) | システム管理者グループ名のパターン     |
| repository_admin | [HasRepoName](#hasreponame) | リポジトリ管理者グループ名のパターン   |
| community_admin  | [HasRepoName](#hasreponame) | コミュニティ管理者グループ名のパターン |
| contributor      | [HasRepoName](#hasreponame) | 投稿ユーザーグループ名のパターン       |
| general_user     | [HasRepoName](#hasreponame) | 一般ユーザーグループ名のパターン       |


## HasRepoId
リポジトリ ID を含むパターンを定義する文字列を示す型エイリアス。
定数 [`HAS_REPO_ID_PATTERN`](./const.md#has_repo_id_pattern) の正規表現にマッチする文字列である。

#### シグネチャ
```python[config.py]
type HasRepoId = ...
```


## HasRepoName
リポジトリ名を含むパターンを定義する文字列を示す型エイリアス。
定数 [`HAS_REPO_NAME_PATTERN`](./const.md#has_repo_name_pattern) の正規表現にマッチする文字列である。

#### シグネチャ
```python[config.py]
type HasRepoName = ...
```


## HasRepoAndUserDefinedId
リポジトリ ID とユーザー定義 ID を含むパターンを定義する文字列を示す型エイリアス。
定数 [`HAS_REPO_ID_AND_USER_DEFINED_ID_PATTERN`](./const.md#has_repo_id_and_user_defined_id_pattern) の正規表現にマッチする文字列である。

#### シグネチャ
```python[config.py]
type HasRepoAndUserDefinedId = ...
```


## CeleryConfig
Celery アプリケーションに関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class CeleryConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前           | 型  | 説明                      |
| -------------- | --- | ------------------------- |
| broker_url     | str | Celery ブローカーの URL   |
| result_backend | str | Celery バックエンドの URL |


## PostgresConfig
Postgres に関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class PostgresConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前     | 型  | 説明                   |
| -------- | --- | ---------------------- |
| user     | str | データベースユーザー名 |
| password | str | データベースパスワード |
| host     | str | データベースホスト名   |
| port     | int | データベースポート番号 |
| db       | str | データベース名         |


## RedisConfig
Redis に関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class RedisConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前           | 型                                           | 説明                           |
| -------------- | -------------------------------------------- | ------------------------------ |
| cache_type     | Literal\["RedisCache", "RedisSentinelCache"] | Redis の接続構成               |
| socket_timeout | int                                          | ソケットタイムアウト（秒）     |
| cache_timeout  | int                                          | キャッシュの有効期限（秒）     |
| key_prefix     | str                                          | キャッシュキーのプレフィックス |
| database       | [RedisDatabaseConfig](#redisdatabaseconfig)  | Redis データベース設定         |
| single         | [RedisSingleConfig](#redissingleconfig)      | Redis 単一接続設定             |
| sentinel       | [RedisSentinelConfig](#redissentinelconfig)  | Redis Sentinel 接続設定        |


## RedisDatabaseConfig
Redis データベース番号に関するサーバー設定値を管理するクラス。 [`RedisConfig`](#redisconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class RedisDatabaseConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

| 名前           | 型  | 説明                                                   |
| -------------- | --- | ------------------------------------------------------ |
| app_cache      | int | アプリケーションのキャッシュに使用するデータベース番号 |
| account_store  | int | アカウントストアに使用するデータベース番号             |
| result_backend | int | Celery の結果バックエンドに使用するデータベース番号    |
| group_cache    | int | グループキャッシュ機能で使用するデータベース番号       |


## RedisSingleConfig
Redis の単一接続に関するサーバー設定値を管理するクラス。 [`RedisConfig`](#redisconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class RedisSingleConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

| 名前     | 型  | 説明                 |
| -------- | --- | -------------------- |
| base_url | str | Redis サーバーの URL |


## RedisSentinelConfig
Redis Sentinel 接続に関するサーバー設定値を管理するクラス。 [`RedisConfig`](#redisconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class RedisSentinelConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前        | 型                                                | 説明                          |
| ----------- | ------------------------------------------------- | ----------------------------- |
| master_name | str                                               | Sentinel マスターノードの名前 |
| nodes       | [list\[SentinelNodeConfig\]](#sentinelnodeconfig) | Sentinel ノードのリスト       |


## SentinelNodeConfig
Redis Sentinel ノードに関するサーバー設定値を管理するクラス。 [`RedisSentinelConfig`](#redissentinelconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class SentinelNodeConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前 | 型  | 説明                    |
| ---- | --- | ----------------------- |
| host | str | Sentinel ノードのホスト |
| port | int | Sentinel ノードのポート |


## RabbitmqConfig
RabbitMQ に関するサーバー設定値を管理するクラス。 [`RuntimeConfig`](#runtimeconfig) でネストした設定値として使用される。

#### シグネチャ
```python[config.py]
class RabbitmqConfig(BaseModel):
```

#### 依存するライブラリ
- **Pydantic**： 設定値の型安全管理に使用。

#### 継承元
`pydantic.BaseModel`

#### クラス属性

| 名前 | 型  | 説明                    |
| ---- | --- | ----------------------- |
| url  | str | RabbitMQ サーバーの URL |


## setup_config
サーバー設定を初期化する関数。

#### シグネチャ
```python[config.py]
def setup_config(path_or_obj: str | RuntimeConfig) -> RuntimeConfig:
```

#### 引数

| 名前        | 型                                     | 説明                                               |
| ----------- | -------------------------------------- | -------------------------------------------------- |
| path_or_obj | str \| [RuntimeConfig](#runtimeconfig) | 設定ファイルのパス、またはサーバー設定インスタンス |

#### 戻り値

| 型                              | 説明                                 |
| ------------------------------- | ------------------------------------ |
| [RuntimeConfig](#runtimeconfig) | 初期化されたサーバー設定インスタンス |

#### 処理概要
1. 引数 `path_or_obj` が文字列の場合、その値をファイルパスとして設定ファイルを読み込み、
  サーバー設定インスタンス [`RuntimeConfig`](#runtimeconfig) を生成する。
1. 戻り値としてサーバー設定インスタンスを返却する。


## config
読み込み済みのサーバー設定にアクセスするためのプロキシとなるグローバル変数。  
アプリケーションのどこからでもサーバー設定にアクセスできる。  

#### シグネチャ
```python[config.py]
config: RuntimeConfig
```

#### 依存するライブラリ
- **Werkzeug**： サーバー設定のインスタンスの遅延取得に使用。
- **Flask**： `current_app` から Flask 拡張を取得するために使用。

#### 処理内容
1. [`LocalProxy`](https://werkzeug.palletsprojects.com/en/stable/local/#werkzeug.local.LocalProxy) を使用し、
   `current_app` から Flask 拡張 [`"jairocloud-groups-manager"`](./ext.md#jairocloudgroupsmanager) を取得し、 `config` 属性を参照する。
