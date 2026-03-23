---
navigation:
  title: はじめに
title: サーバーサイド詳細設計書
description: リポジトリ管理者向けのグループ管理ツール。
headline: JAIRO Cloud Groups Manager
---

## 本書について
本書は、JAIRO Cloud Groups Manager（以降、当システム）のサーバーサイドの詳細設計を記述したものである。


## 前提条件
当システムは、以下のサービスに依存する。
- mAP Core Authorization Server
- mAP Core API V2

また、本機能は以下の環境で動作することを前提とする。
- Python 3.14.x
- Flask 3.1.x
- Celery 5.6.x


## 主要な依存ライブラリ
- **Flask**： Web アプリケーションフレームワーク。REST API やルーティング、リクエスト管理を提供する。
- **SQLAlchemy**： ORM。データベース接続・モデル定義・クエリ発行を担当する。
- **Celery**： 分散タスクキュー。非同期処理（例：グループ作成・更新のバックグラウンド処理）を実現する。
- **Pydantic**： JSON および Python オブジェクト間の型安全なシリアライズ・デシリアライズを行う。
- **Redis**： Celery のバックエンド、セッション管理、キャッシュストアとして利用する。
- **amqp (RabbitMQ)**： Celery のメッセージブローカーとして使用する。

すべての依存関係は、uv で管理され、`pyproject.toml` および `uv.lock` に記録される。
あるいは、 [依存関係グラフ](https://github.com/RCOSDP/jairocloud-groups-manager/network/dependencies) から確認することもできる。
