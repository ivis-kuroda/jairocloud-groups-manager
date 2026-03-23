---
title: signals
description: 当システムのシグナル機能に関する機能を提供する。
---

## repository_created
リポジトリが作成されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
repository_created: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される。


## repository_updated
リポジトリが更新されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
repository_updated: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される。


## repository_deleted
リポジトリが削除されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
repository_deleted: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される。


## group_created
グループが作成されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
group_created: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される。


## group_updated
グループが更新されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
group_updated: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される。


## group_deleted
グループが削除されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
group_deleted: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される。


## user_created
ユーザーが作成されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
user_created: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される


## user_updated
ユーザーが更新されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
user_updated: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される


## user_deleted
ユーザーが削除されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
user_deleted: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される


## user_promoted
ユーザーがシステム管理者に昇格されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
user_promoted: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される


## user_demoted
ユーザーがシステム管理者から降格されたときに発火されるシグナル。

#### シグネチャ
```python[signals.py]
user_demoted: blinker.NamedSignal
```

#### 依存するライブラリ
- **blinker**： シグナル機能を提供するために使用される。
