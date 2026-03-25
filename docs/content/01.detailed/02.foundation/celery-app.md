---
title: celery_app
description: Celery アプリケーションのエントリーポイントを提供する。
---

## celery_app
Celery アプリケーションのエントリポイントとなるグローバル変数。  

#### シグネチャ
```python[celery_app.py]
celery_app: Celery
```

#### 処理内容
1. [`factory:create_app`](./factory.md#create_app) から得た Flask アプリケーションのインスタンスより、 Flask 拡張 `"celery"` として初期化された Celery アプリケーションのインスタンスを取得し、保持する。
