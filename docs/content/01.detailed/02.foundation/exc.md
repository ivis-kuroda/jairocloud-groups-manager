---
title: exc
description: 当システムのビジネスロジックにおける例外定義を提供する。
---

## JAIROCloudGroupsManagerError
当システムのビジネスロジックにおける基底例外クラス。すべてのカスタム例外はこのクラスを継承する。

#### シグネチャ
```python[exc.py]
class JAIROCloudGroupsManagerError(Exception):
```

#### 継承元
`Exception`{lang=python}

#### 属性
| 名前    | 型                                     | 説明                               |
| ------- | -------------------------------------- | ---------------------------------- |
| message | [LogMessage](./messages.md#logmessage) | 例外のエラーメッセージインスタンス |
| code    | str                                    | 例外のエラーコード                 |
| string  | str                                    | エラーメッセージ本文               |

#### メソッド

| 名前                       | 型   | 説明                                     |
| -------------------------- | ---- | ---------------------------------------- |
| &#95;&#95;init&#95;&#95;() | None | クラスの初期化メソッド                   |
| &#95;&#95;str&#95;&#95;()  | str  | 文字列としての振る舞いを提供するメソッド |


### \_\_init__
クラスの初期化メソッド。

#### シグネチャ
```python[exc.py]
def __init__(self, message: str = None) -> None:
```

#### 引数

| 名前    | 型                                     | 説明                               |
| ------- | -------------------------------------- | ---------------------------------- |
| message | [LogMessage](./messages.md#logmessage) | 例外のエラーメッセージインスタンス |

#### 処理内容
1. 引数 `message` の値を属性 `message` に設定する。
2. 属性 `code` に、メッセージのコードを設定する。
3. 属性 `string` に、メッセージ本文を設定する。
4. 継承元クラスの `__init__` メソッドを呼び出す。


### \_\_str\_\__
文字列としての振る舞いを提供するメソッド。エラーコードとエラーメッセージを組み合わせた文字列を返す。

#### シグネチャ
```python[exc.py]
def __str__(self) -> str:
```

#### 戻り値
| 型  | 説明                                       |
| --- | ------------------------------------------ |
| str | エラーコードとエラーメッセージを組み合わせた文字列 |

#### 処理内容
1. 属性 `code` と属性 `string` を組み合わせた文字列を返す。
  `"<code> | <string>"`{lang=python} 形式で返す。

## ConfigurationError
サーバー設定に関する例外クラス。

#### シグネチャ
```python[exc.py]
class ConfigurationError(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## CertificatesError
証明書の操作に関する例外クラス。

#### シグネチャ
```python[exc.py]
class CertificatesError(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## ServiceSettingsError
動的サービス設定の操作に関する基底例外クラス。

#### シグネチャ
```python[exc.py]
class ServiceSettingsError(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## CredentialsError
クライアント認証情報の操作に関する例外クラス。

#### シグネチャ
```python[exc.py]
class CredentialsError(ServiceSettingsError):
```

#### 継承元
`ServiceSettingsError`


## OAuthTokenError
OAuth トークンの操作に関する例外クラス。

#### シグネチャ
```python[exc.py]
class OAuthTokenError(ServiceSettingsError):
```

#### 継承元
`ServiceSettingsError`


## UnsafeOperationError
安全でない操作が拒否されたことを示す例外クラス。

#### シグネチャ
```python[exc.py]
class UnsafeOperationError(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## SystemAdminNotFound
システム管理者が見つからないことを示す例外クラス。

#### シグネチャ
```python[exc.py]
class SystemAdminNotFound(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## InfrastructureError
インフラストラクチャの操作に関する例外クラス。


#### シグネチャ
```python[exc.py]
class InfrastructureError(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## DatabaseError
データベース操作に関する例外クラス。

#### シグネチャ
```python[exc.py]
class DatabaseError(InfrastructureError):
```

#### 継承元
`InfrastructureError`


## DatastoreError
データストア操作に関する例外クラス。

#### シグネチャ
```python[exc.py]
class DatastoreError(InfrastructureError):
```

#### 継承元
`InfrastructureError`


## TaskExcutionError
タスクの実行に関する例外クラス。

#### シグネチャ
```python[exc.py]
class TaskExcutionError(DatastoreError):
```

#### 継承元
`DatastoreError`


## RecordNotFound
レコードが見つからないことを示す例外クラス。

#### シグネチャ
```python[exc.py]
class RecordNotFound(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## InvalidRecordError
レコードが不正であることを示す例外クラス。

#### シグネチャ
```python[exc.py]
class InvalidRecordError(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## ApiClientError
API クライアントの操作に関する基底例外クラス。

#### シグネチャ
```python[exc.py]
class ApiClientError(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## ResourceInvalid
API クライアント操作において、リソースが不正であることを示す例外クラス。

#### シグネチャ
```python[exc.py]
class ResourceInvalid(ApiClientError):
```

#### 継承元
`ApiClientError`


## ResourceNotFound
API クライアント操作において、リソースが見つからないことを示す例外クラス。

#### シグネチャ
```python[exc.py]
class ResourceNotFound(ApiClientError):
```

#### 継承元
`ApiClientError`


## UnexpectedResponseError
API クライアント操作において、予期しないレスポンスが返されたことを示す例外クラス。

#### シグネチャ
```python[exc.py]
class UnexpectedResponseError(ApiClientError):
```

#### 継承元
`ApiClientError`


## ApiRequestError
アプリケーションの API リクエストの処理に関する例外クラス。

#### シグネチャ
```python[exc.py]
class ApiRequestError(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## RequestConflict
API リクエストの処理において、リクエストの内容に競合があることを示す例外クラス。

#### シグネチャ
```python[exc.py]
class RequestConflict(ApiRequestError):
```

#### 継承元
`ApiRequestError`


## InvalidQueryError
API クエリの内容が不正であることを示す例外クラス。

#### シグネチャ
```python[exc.py]
class InvalidQueryError(ApiRequestError):
```

#### 継承元
`ApiRequestError`


## InvalidFormError
リクエストのフォームデータが不正であることを示す例外クラス。

#### シグネチャ
```python[exc.py]
class InvalidFormError(ApiRequestError):
```

#### 継承元
`ApiRequestError`


## BulkOperationError
一括操作の処理に関する例外クラス。

#### シグネチャ
```python[exc.py]
class BulkOperationError(JAIROCloudGroupsManagerError):
```

#### 継承元
`JAIROCloudGroupsManagerError`


## FileValidationError
一括操作で使用されるファイルの内容が不正であることを示す例外クラス。

#### シグネチャ
```python[exc.py]
class FileValidationError(BulkOperationError):
```

#### 継承元
`BulkOperationError`
