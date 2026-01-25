# 文件管理功能实现计划

## 目标

实现 Notebook 内的源文件（Source）管理，包括列表展示、删除、重命名和禁用/启用。

## 核心挑战

目前的存储结构是扁平的 `chunks.json`，没有独立的 `sources.json` 表。

* **Source 定义**：由 `source_id` 唯一标识（通常是文件名或 URL 标题）。

* **聚合逻辑**：需要遍历 chunks 聚合出 Source 列表。

* **状态管理**：需要在 chunks 里增加 `enabled` 字段，或者引入额外的 `sources.json` 来管理元数据（更推荐后者，性能更好且支持重命名）。

## 1. 数据结构升级

引入 `data/notebooks/{id}/sources.json`，存储源文件元数据：

```json
[
  {
    "id": "uuid",
    "name": "foo.pdf",
    "type": "pdf",
    "original_path": "/path/to/foo.pdf",
    "enabled": true,
    "created_at": 1234567890
  }
]
```

同时在 `chunks.json` 中，将 `source_id` 关联到这个 UUID，或者保持现状但通过 `sources.json` 来过滤检索。
**决策**：为了保持兼容性和简单性，我们暂不引入 UUID，继续使用 `source_id`（文件名/URL）作为主键，但在 `ingest` 时生成一份 `sources.json` 以便快速列表和状态管理。

## 2. 后端逻辑 (`app/sources.py`)

* **list\_sources(notebook\_id)**: 读取 `chunks.json`，按 `source_id` 聚合去重，返回列表。（或者维护一个独立的 sources 索引）

  * *优化方案*：直接扫描 `chunks.json` 可能会慢。我们在 `save_chunks` 时同步更新一个 `sources.json` 索引文件。

* **delete\_source(notebook\_id, source\_id)**: 从 `chunks.json` 中删除所有 `source_id` 匹配的条目。

* **update\_source(notebook\_id, source\_id, updates)**:

  * **禁用/启用**：在 `chunks.json` 的所有相关 chunk 中更新 `enabled` 字段（或者在检索时过滤）。

  * **重命名**：批量更新 chunks 里的 `source_id`。

## 3. API 接口 (`app/main.py`)

* `GET /notebooks/{id}/sources`

* `DELETE /notebooks/{id}/sources/{source_id}`

* `PATCH /notebooks/{id}/sources/{source_id}` (body: `{ name: str, enabled: bool }`)

## 4. 前端 UI

* 在“摄取资料”卡片下方，新增一个“已摄取资料”列表。

* 每行展示：图标（PDF/URL）、名称、Switch（启用/禁用）、删除按钮、重命名按钮。

## 实施步骤

1. **数据层**：创建 `SourceManager`，负责对 `chunks.json` 进行增删改查操作。
2. **API**：注册路由。
3. **前端**：实现列表渲染和操作交互。

