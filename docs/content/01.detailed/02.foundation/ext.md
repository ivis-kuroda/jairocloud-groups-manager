---
title: ext
description: Flask アプリケーションの拡張機能を提供する。
---

## JAIROCloudGroupsManager
当システムの全体的な初期化処理を行い、 Flask 拡張として登録するクラス。

#### シグネチャ
```python[ext.py]
class JAIROCloudGroupsManager:
```

#### 属性

| 名前      | 型                                              | 説明                                                                                 |
| --------- | ----------------------------------------------- | ------------------------------------------------------------------------------------ |
| datastore | dict[str, Redis]                                | データストアの接続情報を保持する辞書                                                 |
| _config   | str \| [RuntimeConfig](config.md#runtimeconfig) | （プライベート）サーバー設定のファイルパス、またはサーバー設定インスタンスを保持する |

#### メソッド

| 名前                       | 型   | 説明                                       |
| -------------------------- | ---- | ------------------------------------------ |
| &#95;&#95;init&#95;&#95;() | None | クラスの初期化メソッド                     |
| init_app()                 | None | Flask アプリケーションを初期化するメソッド |
| init_config()              | None | サーバー設定値を初期化するメソッド         |
| init_db_app()              | None | データベースを初期化するメソッド           |
| init_storage()             | None | ストレージを初期化するメソッド             |

#### プロパティ

| 名前   | 型                                       | 説明                     |
| ------ | ---------------------------------------- | ------------------------ |
| config | [RuntimeConfig](config.md#runtimeconfig) | サーバー設定インスタンス |

### \_\_init__
クラスの初期化メソッド。

#### シグネチャ
```python[ext.py]
def __init__(self, app: Flask = None, config: str | RuntimeConfig = None) -> None:
```

#### 引数

| 名前   | 型                                              | デフォルト | 説明                                           |
| ------ | ----------------------------------------------- | ---------- | ---------------------------------------------- |
| app    | Flask                                           | None       | Flask アプリケーションインスタンス             |
| config | str \| [RuntimeConfig](config.md#runtimeconfig) | None       | サーバー設定値のインポート名またはオブジェクト |

#### 処理内容
1. 属性 `config` に引数 `config` の値を設定する。
   引数の指定がなければ、 [`DEFAULT_CONFIG_PATH`](./const.md#default_config_path) を設定する。
2. 引数 `app` が指定されている場合、 [`init_app`](#init_app) メソッドを呼び出す。


### init_app
Flask 拡張として初期化を行うメソッド。

#### シグネチャ
```python[ext.py]
def init_app(self, app: Flask) -> None:
```

#### 引数

| 名前 | 型    | 説明                               |
| ---- | ----- | ---------------------------------- |
| app  | Flask | Flask アプリケーションインスタンス |

#### 処理内容
1. [`init_config`](#init_config) メソッドを呼び出し、サーバー設定値を初期化する。
2. [`logger:setup_logger`](./logger.md#setup_logger) 関数を呼び出し、アプリケーションのロガーの設定を行う。
3. [`init_db_app`](#init_db_app) メソッドを呼び出し、データベースを初期化する。
4. [`login_manager`](./auth.md#login_manager) を初期化する。
5. [`datastore:setup_datastore`](./datastore.md#setup_datastore) メソッドを呼び出し、属性 `datastore` を初期化する。
6. [`api.router:create_api_blueprint`](../04.api/01.router.md#create_api_blueprint) を呼び出し Blueprint を作成し、アプリケーションに登録する。
   URL プレフィックスは `/api` とする。
7. [`storage:init_storage`](#init_storage) メソッドを呼び出し、ストレージを初期化する。
8. 自身を Flask 拡張として `"jairocloud-groups-manager"` の名前で登録する。


### init_config
サーバー設定値を初期化するメソッド。

#### シグネチャ
```python[ext.py]
def init_config(self, app: Flask) -> None:
```

#### 引数

| 名前 | 型    | 説明                               |
| ---- | ----- | ---------------------------------- |
| app  | Flask | Flask アプリケーションインスタンス |

#### 処理内容
1. 属性 `config` の値で [`config:setup_config`](config.md#setup_config) 関数を呼び出し、
  サーバー設定値を初期化する。
1. 引数 `app` の設定オブジェクトにサーバー設定値を登録する。
2. 引数 `app` の設定オブジェクトに環境変数を読み込ませる。


### init_db_app
データベースに関する初期化を行うメソッド。

#### シグネチャ
```python[ext.py]
def init_db_app(self, app: Flask) -> None:
```

#### 引数

| 名前 | 型    | 説明                               |
| ---- | ----- | ---------------------------------- |
| app  | Flask | Flask アプリケーションインスタンス |

#### 依存するライブラリ
- **Flask-SQLAlchemy**： データベース拡張機能の初期化に使用。

#### 処理内容
1. データベース拡張機能を初期化する。
2. テーブルに対応するモデルクラスをインポートし、読み込ませる。


### init_storage
ストレージに関する初期化を行うメソッド。

#### シグネチャ
```python[ext.py]
def init_storage(self, app: Flask) -> None:
```

#### 引数

| 名前 | 型    | 説明                               |
| ---- | ----- | ---------------------------------- |
| app  | Flask | Flask アプリケーションインスタンス |

#### 処理内容
1. サーバー設定値 [`STORAGE.type`](config.md#storage) を参照し、ストレージの種別に応じた初期化を行う。
   現時点ではローカルストレージのみをサポートしているため、ローカルストレージの初期化処理を行う。
   オブジェクトストレージを使用する場合は、ファイルシステムに直接マウントすることで対応する。
    - 設定値が `"local"` の場合、ローカルストレージの初期化処理を行う。
      [`STORAGE.local.temporary`](../02.foundation/config.md#localstorageconfig) を参照し、ディレクトリが存在しない場合は作成する。
      [`STORAGE.local.storage`](../02.foundation/config.md#localstorageconfig) を参照し、ディレクトリが存在しない場合は作成する。
