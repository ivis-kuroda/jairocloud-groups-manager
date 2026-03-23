---
title: const
description: サーバー内で使用される定数を提供する。
---

## DEFAULT_LOG_FORMAT
デフォルトのログフォーマット文字列。
ログメッセージの出力形式を定義するために使用される。

#### シグネチャ
```python[const.py]
DEFAULT_LOG_FORMAT: str
```

#### 値

```python
"[%(asctime)s.%(msecs)03dZ] %(levelname)-8s %(message)s (%(addr)s - %(user)s)"
```


## DEFAULT_LOG_FORMAT_DEV
開発環境向けのデフォルトログフォーマット文字列。
ログメッセージの出力形式を定義するために使用される。

#### シグネチャ
```python[const.py]
DEFAULT_LOG_FORMAT_DEV: str
```

#### 値

```python
"[%(asctime)s.%(msecs)03dZ] %(levelname)-8s %(message)s (%(pathname)s:%(lineno)d)"
```


## DEFAULT_LOG_DATEFMT
デフォルトのログ日付フォーマット文字列。
ログメッセージの日付表示形式を定義するために使用される。

#### シグネチャ
```python[const.py]
DEFAULT_LOG_DATEFMT: str
```

#### 値

```python
"%Y-%m-%dT%H:%M:%S"
```


## DEFAULT_CONFIG_PATH
デフォルトの設定ファイルパス。
アプリケーション起動時に設定ファイルが指定されなかった場合に使用される。

#### シグネチャ
```python[const.py]
DEFAULT_CONFIG_PATH: str
```

#### 値

```python
"configs/server.config.toml"
```

## DEFAULT_SEARCH_COUNT
デフォルトの検索結果の最大件数。
mAP Core API V2 でリソース検索する際や、データベースのクエリでページサイズが指定されない場合に使用される。

#### シグネチャ
```python[const.py]
DEFAULT_SEARCH_COUNT: int
```

#### 値

```python
20
```


## SHIB_HEADERS.EPPN
Shibboleth で ePPN (eduPersonPrincipalName) を表す HTTP ヘッダーの名前。
認証時にユーザーの識別に使用される。

#### シグネチャ
```python[const.py]
SHIB_HEADERS.EPPN: str
```

#### 値

```python
"EPPN"
```


## SHIB_HEADERS.IS_MEMBER_OF
Shibboleth でユーザーの所属グループを表す HTTP ヘッダーの名前。
認証時にユーザーの所属グループやロールの識別に使用される。

#### シグネチャ
```python[const.py]
SHIB_HEADERS.IS_MEMBER_OF: str
```

#### 値

```python
"IS_MEMBER_OF"
```


## SHIB_HEADERS.DISPLAY_NAME
Shibboleth でユーザーの表示名を表す HTTP ヘッダーの名前。
認証時にユーザーの表示名の識別に使用される。

#### シグネチャ
```python[const.py]
SHIB_HEADERS.DISPLAY_NAME: str
```

#### 値

```python
"DISPLAY_NAME"
```


## SHIB_HEADERS.JA_DISPLAY_NAME
Shibboleth でユーザーの日本語表示名を表す HTTP ヘッダーの名前。

#### シグネチャ
```python[const.py]
SHIB_HEADERS.JA_DISPLAY_NAME: str
```

#### 値

```python
"JA_DISPLAY_NAME"
```


## MAP_USER_SCHEMA
mAP Core API V2 のユーザーリソースのスキーマ識別子。
ユーザー情報の取得や操作に使用される。

#### シグネチャ
```python[const.py]
MAP_USER_SCHEMA: str
```

#### 値

```python
"urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:User"
```


## MAP_GROUP_SCHEMA
mAP Core API V2 のグループリソースのスキーマ識別子。
グループ情報の取得や操作に使用される。

#### シグネチャ
```python[const.py]
MAP_GROUP_SCHEMA: str
```

#### 値

```python
"urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Group"
```

## MAP_SERVICE_SCHEMA
mAP Core API V2 のサービスリソースのスキーマ識別子。
サービス情報の取得や操作に使用される。

#### シグネチャ
```python[const.py]
MAP_SERVICE_SCHEMA: str
```

#### 値

```python
"urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Service"
```


## MAP_LIST_RESPONSE_SCHEMA
mAP Core API V2 のリストレスポンスのスキーマ識別子。
リスト形式のレスポンスの取得や操作に使用される。

#### シグネチャ
```python[const.py]
MAP_LIST_RESPONSE_SCHEMA: str
```

#### 値

```python
"urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:ListResponse"
```


## MAP_ERROR_SCHEMA
mAP Core API V2 のエラーレスポンスのスキーマ識別子。
API エラー情報の取得や操作に使用される。

#### シグネチャ
```python[const.py]
MAP_ERROR_SCHEMA: str
```

#### 値

```python
"urn:ietf:params:scim:schemas:mace:gakunin.jp:core:2.0:Error"
```


## MAP_PATCH_SCHEMA
mAP Core API V2 のパッチリクエストのスキーマ識別子。
パッチ情報の取得や操作に使用される。

#### シグネチャ
```python[const.py]
MAP_PATCH_SCHEMA: str
```

#### 値

```python
"urn:ietf:params:scim:api:messages:2.0:PatchOp"
```


## MAP_BULK_REQUEST_SCHEMA
mAP Core API V2 の一括リクエストのスキーマ識別子。
一括操作のリクエストに使用される。

#### シグネチャ
```python[const.py]
MAP_BULK_REQUEST_SCHEMA: str
```

#### 値

```python
"urn:ietf:params:scim:api:messages:2.0:BulkRequest"
```


## MAP_BULK_RESPONSE_SCHEMA
mAP Core API V2 の一括レスポンスのスキーマ識別子。
一括操作のレスポンスに使用される。

#### シグネチャ
```python[const.py]
MAP_BULK_RESPONSE_SCHEMA: str
```

#### 値

```python
"urn:ietf:params:scim:api:messages:2.0:BulkResponse"
```


## MAP_OAUTH_ISSUE_ENDPOINT
mAP Core Authorization Server のクライアント認証エンドポイントの URL パス。
クライアント ID およびシークレットの取得に使用される。

#### シグネチャ
```python[const.py]
MAP_OAUTH_ISSUE_ENDPOINT: str
```

#### 値

```python
"/oauth/sslauth/issue.php"
```


## MAP_OAUTH_AUTHORIZE_ENDPOINT
mAP Core Authorization Server の認可エンドポイントの URL パス。
OAuth2.0 の認可コードの取得に使用される。

#### シグネチャ
```python[const.py]
MAP_OAUTH_AUTHORIZE_ENDPOINT: str
```

#### 値

```python
"/oauth/shib/authrequest.php"
```


## MAP_OAUTH_TOKEN_ENDPOINT
mAP Core Authorization Server のトークンエンドポイントの URL パス。
アクセストークンおよびリフレッシュトークンの取得に使用される。

#### シグネチャ
```python[const.py]
MAP_OAUTH_TOKEN_ENDPOINT: str
```

#### 値

```python
"/oauth/token.php"
```


## MAP_OAUTH_CHECK_ENDPOINT
mAP Core Authorization Server のトークンの有効性確認エンドポイントの URL パス。
アクセストークンの有効性確認に使用される。

#### シグネチャ
```python[const.py]
MAP_OAUTH_CHECK_ENDPOINT: str
```

#### 値

```python
"/oauth/resource.php"
```


## MAP_USERS_ENDPOINT
mAP Core API V2 のユーザーリソースエンドポイントの URL パス。
ユーザー情報の取得や操作に使用される。

#### シグネチャ
```python[const.py]
MAP_USERS_ENDPOINT: str
```

#### 値

```python
"/api/v2/Users"
```


## MAP_EXIST_EPPN_ENDPOINT
mAP Core API V2 の ePPN 存在確認エンドポイントの URL パス。
ePPN に基づいてユーザーの存在確認に使用される。

#### シグネチャ
```python[const.py]
MAP_EXIST_EPPN_ENDPOINT: str
```

#### 値

```python
"/api/v2/Existeppn"
```


## MAP_SELF_ENDPOINT
mAP Core API V2 の OAuth2.0 認証ユーザー情報エンドポイントの URL パス。
アクセストークンを使用して認証されたユーザーの情報の取得に使用される。

#### シグネチャ
```python[const.py]
MAP_SELF_ENDPOINT: str
```

#### 値

```python
"/api/v2/Self"
```


## MAP_GROUPS_ENDPOINT
mAP Core API V2 のグループリソースエンドポイントの URL パス。
グループ情報の取得や操作に使用される。

#### シグネチャ
```python[const.py]
MAP_GROUPS_ENDPOINT: str
```

#### 値

```python
"/api/v2/Groups"
```


## MAP_SERVICES_ENDPOINT
mAP Core API V2 のサービスリソースエンドポイントの URL パス。
サービス情報の取得や操作に使用される。

#### シグネチャ
```python[const.py]
MAP_SERVICES_ENDPOINT: str
```

#### 値

```python
"/api/v2/Services"
```


## MAP_BULK_ENDPOINT
mAP Core API V2 の一括リクエストエンドポイントの URL パス。
一括操作に使用される。

#### シグネチャ
```python[const.py]
MAP_BULK_ENDPOINT: str
```

#### 値

```python
"/api/v2/Bulk"
```

## MAP_DEFAULT_SEARCH_COUNT
mAP Core API V2 の検索リクエストのデフォルトの最大件数。
検索リクエストでページサイズが指定されない場合に使用される。

#### シグネチャ
```python[const.py]
MAP_DEFAULT_SEARCH_COUNT: int
```

#### 値

```python
20
```

## MAP_NOT_FOUND_PATTERN
mAP Core API V2 のリソースが見つからない場合のエラーメッセージのパターン。
エラーメッセージの解析やエラー処理に使用される。

#### シグネチャ
```python[const.py]
MAP_NOT_FOUND_PATTERN: str
```

#### 値

```python
r"'(.*)' Not Found"
```


## MAP_DUPLICATE_ID_PATTERN
mAP Core API V2 のリソースの ID が重複している場合のエラーメッセージのパターン。
エラーメッセージの解析やエラー処理に使用される。

#### シグネチャ
```python[const.py]
MAP_DUPLICATE_ID_PATTERN: str
```

#### 値

```python
r"Duplicate id '(.*)'"
```


## MAP_ALREADY_TIED_PATTERN
mAP Core API V2 の 既に ePPN がユーザーリソースに関連付けられている場合のエラーメッセージのパターン。
エラーメッセージの解析やエラー処理に使用される。

#### シグネチャ
```python[const.py]
MAP_ALREADY_TIED_PATTERN: str
```

#### 値

```python
r"(.*) is already tied to another account"
```


## MAP_ILLEGAL_EPPN_PATTERN
mAP Core API V2 の ePPN が不正な形式である場合のエラーメッセージのパターン。
エラーメッセージの解析やエラー処理に使用される。

#### シグネチャ
```python[const.py]
MAP_ILLEGAL_EPPN_PATTERN: str
```

#### 値

```python
r"'(.*)' illegal (eduPersonPrincipalNames needs idpEntityId)"
```

## MAP_NO_RIGHTS_CREATE_PATTERN
mAP Core API V2 のアクセストークンにリソースの作成権限がない場合のエラーメッセージのパターン。
エラーメッセージの解析やエラー処理に使用される。

#### シグネチャ
```python[const.py]
MAP_NO_RIGHTS_CREATE_PATTERN: str
```

#### 値

```python
r"You do not have creation right of '(.*)'"
```

## MAP_NO_RIGHTS_UPDATE_PATTERN
mAP Core API V2 のアクセストークンにリソースの更新権限がない場合のエラーメッセージのパターン。
エラーメッセージの解析やエラー処理に使用される。

#### シグネチャ
```python[const.py]
MAP_NO_RIGHTS_UPDATE_PATTERN: str
```

#### 値

```python
r"No update rights for '(.*)'"
```

## MAP_NO_RIGHTS_APPEND_PATTERN
mAP Core API V2 のアクセストークンにリソースの属性に追加権限がない場合のエラーメッセージのパターン。
エラーメッセージの解析やエラー処理に使用される。

#### シグネチャ
```python[const.py]
MAP_NO_RIGHTS_APPEND_PATTERN: str
```

#### 値

```python
r"No append rights for '(.*)'"
```


## GROUP_DEFAULT_PUBLIC
グループのデフォルトの公開設定。
グループ作成時に公開設定のデフォルト値として使用される。

#### シグネチャ
```python[const.py]
GROUP_DEFAULT_PUBLIC: bool
```

#### 値

```python
False
```


## GROUP_DEFAULT_MEMBER_LIST_VISIBILITY
グループのデフォルトのメンバーリスト表示設定。
グループ作成時にメンバーリスト表示設定のデフォルト値として使用される。

#### シグネチャ
```python[const.py]
GROUP_DEFAULT_MEMBER_LIST_VISIBILITY: Literal["Public", "Private", "Hidden"]
```

#### 値

```python
"Private"
```

<span id="user_role" />

## USER_ROLES.SYSTEM_ADMIN
システム管理者ユーザーの役割を表す定数文字列。

#### シグネチャ
```python[const.py]
USER_ROLES.SYSTEM_ADMIN: str
```

#### 値

```python
"system_admin"
```


## USER_ROLES.REPOSITORY_ADMIN
リポジトリ管理者ユーザーの役割を表す定数文字列。

#### シグネチャ
```python[const.py]
USER_ROLES.REPOSITORY_ADMIN: str
```

#### 値
```python
"repository_admin"
```


## USER_ROLES.COMMUNITY_ADMIN
コミュニティ管理者ユーザーの役割を表す定数文字列。

#### シグネチャ
```python[const.py]
USER_ROLES.COMMUNITY_ADMIN: str
```

#### 値
```python
"community_admin"
```

## USER_ROLES.CONTRIBUTOR
投稿ユーザーの役割を表す定数文字列。

#### シグネチャ
```python[const.py]
USER_ROLES.CONTRIBUTOR: str
```

#### 値
```python
"contributor"
```


## USER_ROLES.GENERAL_USER
一般ユーザーの役割を表す定数文字列。

#### シグネチャ
```python[const.py]
USER_ROLES.GENERAL_USER: str
```

#### 値
```python
"general_user"
```


## HAS_REPO_ID_PATTERN
リポジトリ ID を含むテンプレート文字列の正規表現。
SP コネクタ ID やロールグループ ID など、リポジトリ ID を含む文字列パターンを定義するサーバー設定値の検証に使用される。  
リポジトリ ID を `{repository_id}` というプレースホルダで表現したテンプレート文字列であることを要求する。


#### シグネチャ
```python[const.py]
HAS_REPO_ID_PATTERN: str
```

#### 値

```python
r".*\{repository_id\}.*"
```


## HAS_REPO_ID_AND_USER_DEFINED_ID_PATTERN
リポジトリ ID とユーザー定義 ID を含むテンプレート文字列の正規表現。
ユーザー定義グループの ID など、リポジトリ ID とユーザー定義 ID を含む文字列パターンを定義するサーバー設定値の検証に使用される。  
リポジトリ ID を `{repository_id}` 、ユーザー定義 ID を `{user_defined_id}` というプレースホルダで表現したテンプレート文字列であることを要求する。

#### シグネチャ
```python[const.py]
HAS_REPO_ID_AND_USER_DEFINED_ID_PATTERN: str
```

#### 値

```python
r".*\{repository_id\}.*\{user_defined_id\}.*"
```


## HAS_REPO_NAME_PATTERN
リポジトリ名を含むテンプレート文字列の正規表現。
ロールグループ名など、リポジトリ名を含む文字列パターンを定義するサーバー設定値の検証に使用される。  
リポジトリ名を `{repository_name}` というプレースホルダで表現したテンプレート文字列であることを要求する。

#### シグネチャ
```python[const.py]
HAS_REPO_NAME_PATTERN: str
```

#### 値

```python
r".*\{repository_name\}.*"
```


## IS_MEMBER_OF_PATTERN
Shibboleth の IS_MEMBER_OF ヘッダーから所属グループの ID を抽出するための正規表現。
以下の条件に基づいて所属グループの ID を抽出することを想定している。
- URLにパスセグメント「 /gr/ 」が含まれること。
- グループIDが「 /gr/ 」の直後に続く部分文字列であること。
- グループIDに「 / 」または「 ; 」文字が含まれないこと。
- URLはセミコロン（「 ; 」）または文字列の末尾で終了する。
- 「 /admin 」で終わるURLは一致対象から除外される。

#### シグネチャ
```python[const.py]
IS_MEMBER_OF_PATTERN: str
```

#### 値

```python
r"/gr/([^/;]+)(?=;|$)(?!/admin)"
```

