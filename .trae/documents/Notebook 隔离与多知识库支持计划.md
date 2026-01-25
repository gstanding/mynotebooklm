# Notebook 隔离功能实现计划

## 目标
将目前的单体知识库改造为支持多 Notebook 管理的系统。用户可以创建多个独立的 Notebook（如“Python学习”、“旅游攻略”），每个 Notebook 拥有独立的文件列表和检索索引，互不干扰。

## 1. 数据结构重构
### 目录结构调整
- 原：`data/chunks.json`
- 新：
  - `data/notebooks.json`：存储 Notebook 列表元数据（id, title, created_at 等）。
  - `data/notebooks/{notebook_id}/chunks.json`：每个 Notebook 独立的分块数据。
  - `data/notebooks/{notebook_id}/index.pkl`：(可选) 预计算的索引文件，加速加载。

### 新增数据模型
- **Notebook**: `{ id: str, title: str, created_at: float }`

## 2. 后端 API 改造
### 新增 Notebook 管理接口
- `GET /notebooks`：列出所有 Notebook。
- `POST /notebooks`：创建新 Notebook。
- `DELETE /notebooks/{id}`：删除 Notebook。

### 改造现有接口 (增加 `notebook_id` 参数)
- `POST /ingest` -> `POST /notebooks/{id}/ingest`
- `POST /query` -> `POST /notebooks/{id}/query`
- `GET /status` -> `GET /notebooks/{id}/status`

### 核心逻辑调整
- **Ingest**: 摄取时需指定目标 Notebook，将 chunks 写入对应的 `data/notebooks/{id}/chunks.json`。
- **Index**: 服务启动时不再加载全局索引。改为在第一次访问某个 Notebook 时懒加载其索引，或维护一个 `Dict[str, Index]` 的全局缓存。

## 3. 前端 UI 升级
- **首页 (Home)**：改造为 Notebook 列表页，展示卡片式入口。
- **Notebook 详情页**：点击卡片进入，包含：
  - 侧边栏：当前 Notebook 的文件列表（可删除文件）。
  - 主区域：对话框（仅检索当前 Notebook 内容）。
  - 顶部栏：Notebook 标题、设置入口。

## 实施步骤
1. **数据层**：创建 `NotebookManager` 类，负责目录创建和元数据管理。
2. **后端路由**：新增 `routers/notebooks.py`，迁移并改造 `ingest/query` 逻辑。
3. **前端页面**：新建 `index.html` (列表) 和 `notebook.html` (详情)，或在现有 SPA 中增加路由状态。

我们先从后端数据结构和 API 改造开始。