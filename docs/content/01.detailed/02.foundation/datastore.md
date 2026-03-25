---
title: datastore
description: 当システムのデータストア（揮発性ストレージ）に関する機能を提供する。
---

## setup_datastore
データストアを参照するための初期化処理を行う。アプリケーションの起動時に一度だけ呼び出されることを想定している。

#### シグネチャ
```python[datastore.py]
def setup_datastore(app: Flask, config: RuntimeConfig) -> dict[str, Redis]:
```

#### 引数

| 名前   | 型                                         | 説明                                 |
| ------ | ------------------------------------------ | ------------------------------------ |
| app    | Flask                                      | Flask アプリケーションのインスタンス |
| config | [RuntimeConfig](./config.md#runtimeconfig) | サーバー設定値のインスタンス         |

#### 戻り値
| 型                | 説明                                     |
| ----------------- | ---------------------------------------- |
| dict\[str, Redis] | データストアのインスタンスを格納した辞書 |

#### 処理内容
1. サーバー設定値 [`DATASTORE`](./config.md#datastoreconfig) から、データストアの設定を取得する。
2. データストアごとに [`connection`](#connection) を呼び出し、データストアを参照するインスタンスを作成する。
3. データストアの名前をキー、作成したインスタンスを値とする辞書を作成し、戻り値として返す。

## connection
データストアへの接続を提供する。データストアのインスタンスを返す。データストアとして Redis を使用する。

#### シグネチャ
```python[datastore.py]
def connection(
    app: Flask | None = None, *, db: int, config: RuntimeConfig | None = None
) -> Redis:
```

#### 依存するライブラリ
- **redis-py**： Redis クライアントライブラリ。データストアへの接続を提供するために使用される。

#### 引数

| 名前   | 型                                         | 説明                                 |
| ------ | ------------------------------------------ | ------------------------------------ |
| app    | Flask                                      | Flask アプリケーションのインスタンス |
| db     | int                                        | データストアのデータベース番号       |
| config | [RuntimeConfig](./config.md#runtimeconfig) | サーバー設定値のインスタンス         |

#### 戻り値

| 型    | 説明                       |
| ----- | -------------------------- |
| Redis | データストアのインスタンス |

#### 処理内容
1. サーバー設定値 [`REDIS.cache_type`](./config.md#redisconfig) を確認し、接続構成を決定する。
2. 接続構成に応じた Redis クライアントのインスタンスを作成する。
    - **Redis** の場合： サーバー設定値 [`REDIS.single.base_url`](./config.md#redissingleconfig) および
      引数 `db` を使用して Redis クライアントのインスタンスを作成する。
    - **Redis Sentinel** の場合： サーバー設定値 [`REDIS.sentinel.master_name`](./config.md#redissentinelconfig) および
      [`REDIS.sentinel.nodes`](./config.md#redissentinelconfig) を使用して Redis Sentinel クライアントのインスタンスを作成する。
    - ソケットタイムアウトにはサーバー設定値 [`REDIS.socket_timeout`](./config.md#redisconfig) を使用する。
3. Redis クライアントに対して、接続確認のための PING コマンドを送信する。
   エラーが発生した場合は、警告ログを出力する。
4. 作成した Redis クライアントのインスタンスを戻り値として返す。


## app_cache
アプリケーション全体で使用するキャッシュを提供する。データストアのインスタンスを返す。

#### シグネチャ
```python[datastore.py]
app_cache: Redis
```

## account_store
アカウント情報を格納するためのストアを提供する。データストアのインスタンスを返す。

#### シグネチャ
```python[datastore.py]
account_store: Redis
```

## group_cache
グループ情報を格納するためのストアを提供する。データストアのインスタンスを返す。

#### シグネチャ
```python[datastore.py]
group_cache: Redis
```
