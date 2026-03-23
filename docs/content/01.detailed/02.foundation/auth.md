---
title: auth
description: 当システムの認証機能に関する機能を提供する。
---

## login_manager
Flask-Login の `LoginManager` のインスタンス。

#### シグネチャ
```python[auth.py]
login_manager: LoginManager
```

#### 依存するライブラリ
- **Flask-Login**： クライアントのセッション管理を行うために使用される。


## is_user_logged_in
ユーザーがログインしているかどうかを判定する。
型ガード関数であり、戻り値が真の場合、ユーザーがログインしていることを示す
[`LoginUser`](../03.entities/02.login-user.md#loginuser) 型であることを保証する。

#### 依存するライブラリ
- **Flask-Login**： 現在のユーザーの認証状態を取得するために使用される。

#### シグネチャ
```python[auth.py]
def is_user_logged_in() -> TypeGuard[LoginUser]:
```

#### 戻り値
| 型   | 説明                                    |
| ---- | --------------------------------------- |
| bool | ユーザーがログインしている場合は `True` |

#### 処理内容
1. Flask-Login の `current_user` を使用して、認証済みであるかどうかを判定する。
   認証済みであれば `True`{lang=python} を返し、そうでなければ `False`{lang=python} を返す。
3. `AttributeError` が発生した場合は、ユーザーがログインしていないとみなし `False`{lang=python} を返す。


## refresh_session
アカウントストアのセッション情報の期限を更新する関数。
API の呼び出しごとに実行されることを想定している。

#### シグネチャ
```python[auth.py]
def refresh_session() -> None
```

#### 処理内容
1. サーバー設定値 [`SESSION.strategy`](./config.md#sessionconfig) からセッション管理の戦略を取得し、スライディングセッションでなければ、処理を終了する。
2. [`is_user_logged_in`](#is_user_logged_in) を呼び出し、ユーザーがログイン済みでない場合は処理を終了する。
3. Flask のリクエストセッションからセッション ID を取得する。
4. セッション ID を引数に [`build_account_store_key`](#build_account_store_key) を呼び出し、アカウントストアのキーを生成する。
5. キーをもとにアカウントストアからアカウント情報を取得する。
6. アカウント情報に含まれるログイン日時と現在時刻を比較し、サーバー設定値 [`SESSION.absolute_lifetime`](./config.md#sessionconfig) の絶対有効期限を超えている場合は、アカウントストアから該当するキーを削除し、処理を終了する。
7. サーバー設定値 [`SESSION.sliding_lifetime`](./config.md#sessionconfig) のスライディング有効期限が 0 以上であれば、アカウント情報の有効期限をスライディング有効期限で再設定する。

#### 備考
- API の呼び出しごとにこの関数を実行するためには、アプリケーションの `before_request_funcs` に登録しておく必要がある。


## load_user
Flask-Login へログインユーザーのインスタンスを提供する。
ユーザーローダーとして登録される。

#### シグネチャ
```python[auth.py]
@login_manager.user_loader
def load_user(eppn: str) -> LoginUser | None:
```

#### 依存するライブラリ
- **Flask-Login**： 関数をユーザーローダーとして登録するために使用される。

#### デコレータ
- `@login_manager.user_loader`{lang=python}： Flask-Login のユーザーローダーとして関数を登録するためのデコレータ。

#### 引数

| 名前 | 型  | 説明                                             |
| ---- | --- | ------------------------------------------------ |
| eppn | str | ログインユーザーの edupersonPrincipalName (ePPN) |

#### 戻り値

| 型                                                     | 説明                         |
| ------------------------------------------------------ | ---------------------------- |
| [LoginUser](../03.entities/02.login-user.md#loginuser) | ログインユーザーインスタンス |
| None                                                   | ユーザーが見つからない場合。 |

#### 処理内容
1. リクエストセッションからセッション ID を取得する。
2. セッション ID を引数に [`get_user_from_store`](#get_user_from_store) を呼び出し、アカウントストアからユーザーのインスタンスを取得する。
3. 引数 `eppn` がユーザーのインスタンスに含まれる ePPN と一致しない場合は、`None`{lang=python} を返す。
4. ユーザーのインスタンスを戻り値として返す。


## get_user_from_store
アカウントストアからセッション ID をもとにアカウント情報を取得し、ユーザーのインスタンスを生成する。

#### シグネチャ
```python[auth.py]
def get_user_from_store(session_id: str) -> LoginUser | None:
```

#### 引数

| 名前       | 型  | 説明          |
| ---------- | --- | ------------- |
| session_id | str | セッション ID |

#### 戻り値

| 型                                                     | 説明                         |
| ------------------------------------------------------ | ---------------------------- |
| [LoginUser](../03.entities/02.login-user.md#loginuser) | ログインユーザーインスタンス |
| None                                                   | ユーザーが見つからない場合。 |

#### 処理内容
1. 引数セッション ID を引数に [`build_account_store_key`](../04.api/10.helper.md#build_account_store_key) を呼び出し、キーを生成する。
2. キーをもとにアカウントストアからアカウント情報を取得する。
3. アカウント情報が存在しない場合は `None`{lang=python} を返す。
4. アカウント情報をもとに [`LoginUser`](../03.entities/02.login-user.md#loginuser) のインスタンスを作成し、戻り値として返す。
   アカウントストアから取得したアカウント情報は バイト列である可能性があるため、必要に応じてデコード処理を行う。


## build_account_store_key
セッション ID をもとにセッション情報を取得するキーを作成する。

#### シグネチャ
```python[auth.py]
def build_account_store_key(session_id:str) -> str:
```

#### 引数

| 名前       | 型  | 説明          |
| ---------- | --- | ------------- |
| session_id | str | セッション ID |

#### 戻り値

| 型  | 説明                         |
| --- | ---------------------------- |
| str | アカウントストアのキー文字列 |

#### 処理内容
1. サーバー設定値 [`REDIS.key_prefix`](./config.md#redisconfig) からプレフィックスを取得し セッション ID と結合する。
   `"<key_prefix>_login_<session_id>"` の形式で文字列を生成する。
2. 結合した文字列を戻り値として返す。
