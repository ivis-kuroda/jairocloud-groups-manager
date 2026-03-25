---
title: factory
description: アプリケーションのファクトリ関数を提供する。
---

## create_app
アプリケーションファクトリ関数。 Flask アプリケーションを初期化する。  

#### シグネチャ
```python[factory.py]
@overload
def create_app(import_name: str) -> Flask: ...
@overload
def create_app(import_name: str, *, config_path: str) -> Flask: ...
@overload
def create_app(import_name: str, *, config: RuntimeConfig) -> Flask: ...

def create_app(import_name: str, config_path: Any = None, config: Any = None) -> Flask:
```

#### 引数

| 名前        | 型                                         | デフォルト | 説明                                       |
| ----------- | ------------------------------------------ | ---------- | ------------------------------------------ |
| import_name | str                                        | -          | Flask アプリケーションのインポート名       |
| config_path | str                                        | None       | （オーバーロード）設定ファイルのパス       |
| config      | [RuntimeConfig](./config.md#runtimeconfig) | None       | （オーバーロード）サーバー設定インスタンス |

#### 戻り値

| 型    | 説明                                            |
| ----- | ----------------------------------------------- |
| Flask | 初期化された Flask アプリケーションインスタンス |

#### 依存するライブラリ
- **Flask**： サーバーサイドアプリケーションフレームワークとして使用。

#### 処理概要
1. 引数 `import_name` を使用して Flask アプリケーションのインスタンスを生成する。
2. Flask 拡張 [`ext:JAIROCloudGroupsManager`](./ext.md#jairocloudgroupsmanager) をアプリケーションインスタンスで初期化する。
  このとき、引数 `config_path` または `config` を渡す。
3. [`celery_init_app`](#celery_init_app) を呼び出し、 Celery アプリケーションを初期化する。
4. 初期化された Flask アプリケーションインスタンスを戻り値として返却する。


## celery_init_app
Celery アプリケーションを生成するファクトリ関数。 Flask 拡張として初期化を行う。

#### シグネチャ
```python[factory.py]
def celery_init_app(app: Flask) -> Celery:
```

#### 引数

| 名前 | 型    | 説明                               |
| ---- | ----- | ---------------------------------- |
| app  | Flask | Flask アプリケーションインスタンス |

#### 戻り値

| 型     | 説明                                |
| ------ | ----------------------------------- |
| Celery | Celery アプリケーションインスタンス |

#### 依存するライブラリ
- **Celery**： 非同期タスクの実行と管理に使用。

#### 処理概要
1. Celery アプリケーションのインスタンスを生成する。
   このとき、タスクが Flask アプリケーションのコンテキスト内で実行されるように設定する。
2. 引数 `app` から設定値 `CELERY` を取得し、 Celery アプリケーションの設定に登録する。
3. Celery アプリケーションを Flask 拡張として `"celery"` という名前で登録する。
4. 初期化済みの Celery アプリケーションインスタンスを戻り値として返却する。
