---
title: logger
description: 当システムのアプリケーションログに関する機能を提供する。
---

## setup_logger
アプリケーションログのロガーを設定する機能を提供する。

#### シグネチャ
```python[logger.py]
def setup_logger(app: Flask, config: RuntimeConfig) -> None:
```

#### 引数

| 名前   | 型                                       | 説明                               |
| ------ | ---------------------------------------- | ---------------------------------- |
| app    | Flask                                    | Flask アプリケーションインスタンス |
| config | [RuntimeConfig](config.md#runtimeconfig) | サーバー設定インスタンス           |

#### 処理内容
1. ログレベル設定 [`LOG.level`](config.md#logconfig) に基づいて、アプリケーションのロガーのログレベルを設定する。
2. アプリケーションログから標準出力に出力するハンドラーを取得する。
   ハンドラーが存在しない場合は新規に作成し、アプリケーションのロガーに追加する。
3. ハンドラーのログレベルを設定を [`LOG.level`](config.md#logconfig) に基づいて設定する。
4. ログのフォーマッタを作成し、ハンドラーに設定する。
    - ログフォーマットはサーバー設定値 [`LOG.format`](config.md#logconfig) および [`LOG.datefmt`](config.md#logconfig) に基づく。
    - `LOG.format` が未設定の場合は [`DEFAULT_LOG_FORMAT`](./const.md#default_log_format) を使用する。
    - `LOG.datefmt` が未設定の場合は [`DEFAULT_LOG_DATEFMT`](./const.md#default_log_datefmt) を使用する。
    - 開発環境モード（ `app.config["ENV"]` が `"development"` または `app.debug` が `True` ）の場合は、[`DEFAULT_LOG_FORMAT_DEV`](./const.md#default_log_format_dev) を使用する。
    - タイムスタンプは協定世界時 (UTC) で出力されるように設定する。
5. ハンドラーにフィルター [`_request_context_filter`](#_request_context_filter) を追加する。


## _request_context_filter
ログレコードにリクエストコンテキスト情報を追加するフィルター。

#### シグネチャ
```python[logger.py]
def _request_context_filter(record: LogRecord) -> Literal[True]:
```

#### 引数
| 名前   | 型        | 説明         |
| ------ | --------- | ------------ |
| record | LogRecord | ログレコード |

#### 戻り値
| 型            | 説明               |
| ------------- | ------------------ |
| Literal[True] | 常に True を返す。 |

#### 処理内容
1. ログレコード `record` に属性 `addr` を追加する。
    - Flask のリクエストコンテキストが存在する場合、クライアントの IP アドレスを設定する。  
      リクエストに X-Forwarded-For ヘッダーが存在する場合はその最初の値を使用し、存在しない場合は `request.remote_addr` を使用する。
    - リクエストコンテキストが存在しない場合は `"unknown"` として設定する。
2. ログレコード `record` に属性 `user` を追加する。
    - Flask-Login の `current_user` から ePPN を取得して設定する。
    - 認証されていない場合は `"anonymous"` として設定する。
3. 戻り値として `True` を返す。
