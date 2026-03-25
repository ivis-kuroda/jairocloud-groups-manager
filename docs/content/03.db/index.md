---
navigation:
  title: はじめに
title: テーブル定義書
description: リポジトリ管理者向けのグループ管理ツール。
headline: JAIRO Cloud Groups Manager
---

## 本書について
本書は、JAIRO Cloud Groups Manager（以降、当システム）が利用するデータベースのテーブル定義を記述したものである。


## 前提条件
当システムは、データベースとして PostgreSQL を利用することを前提とする。


## 制約名命名規則

| 制約種別     | 命名規則                                                    |
| ------------ | ----------------------------------------------------------- |
| 主キー       | pk_%(table_name)s                                           |
| ユニーク     | uq_%(table_name)s_%(column_0_name)s                         |
| インデックス | ix_%(column_0_label)s                                       |
| チェック     | ck_%(table_name)s_%(constraint_name)s                       |
| 外部キー     | fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s |
