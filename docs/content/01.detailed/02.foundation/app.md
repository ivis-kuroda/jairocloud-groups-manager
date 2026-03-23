---
title: app
description: アプリケーションのエントリーポイントを提供する。
---

## app

アプリケーションのエントリポイントとなるグローバル変数。  
[`factory:create_app`](factory.md#create_app) から得た Flask アプリケーションインスタンスを保持する。 WSGI サーバーの起動に利用する。

#### シグネチャ
```python[app.py]
app: Flask
```
