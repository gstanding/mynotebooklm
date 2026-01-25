# MyNotebookLM

MyNotebookLM 是一个开源的本地知识库问答系统（MVP），对标 Google NotebookLM。它允许你构建私有的知识库，并通过 AI 对资料进行基于引用的问答。本项目特别针对中文语境和复杂网页抓取进行了深度优化，且无需依赖庞大的向量数据库，架构极其轻量。

## 核心特性 (v0.3.0)

### 1. 多知识库管理 (Notebook Isolation)
- **空间隔离**：支持创建多个独立的 Notebook（如“Python学习”、“旅游计划”），每个 Notebook 的资料完全物理隔离，检索互不干扰。
- **文件管理**：提供可视化的文件列表，支持**查看、删除、禁用/启用**特定文件。禁用文件后，其内容会立即排除在检索范围之外。

### 2. 全能资料摄取 (Robust Ingestion)
- **多源支持**：支持 PDF、本地文本/Markdown、网页 URL。
- **智能爬虫**：内置 Requests -> Pyppeteer -> Raw HTML 三级回退策略。
  - **抗反爬/SPA**：自动识别骨架屏，调用无头浏览器动态渲染，完美支持掘金、知乎等单页应用（SPA）。
  - **环境兼容**：解决了 macOS 下的 Pyppeteer 权限与 SSL 证书问题，开箱即用。

### 3. 混合检索增强 (Hybrid Retrieval)
摒弃单一的关键词匹配，采用多路召回策略：
- **BM25** (0.6)：传统的关键词精准匹配。
- **Jaccard** (0.25)：词集合重叠度，提升短语变体的召回。
- **Trigram** (0.15)：字符级三元组匹配，解决分词错误和模糊匹配问题。
*注：内置 jieba 中文分词，无需外部依赖。*

### 4. 生成式问答 (Generative QA)
- **LLM 接入**：通过自定义网关接入 **DeepSeek V3.2** 模型，基于检索到的资料生成流畅回答。
- **引用溯源**：每一句回答都严格基于本地资料，并在 UI 上标注来源（如 `[1] 掘金首页 - page 1`），拒绝 AI 幻觉。

## 快速开始

### 1. 环境准备
确保 Python 3.6+ 环境。
```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动服务
你需要配置 DeepSeek API Key（或兼容 OpenAI 格式的其他 LLM Key）以启用生成式问答。

```bash
# 设置 API Key (示例)
export DEEPSEEK_API_KEY="sk-xxxxxxxx"

# 启动服务
uvicorn app.main:app --reload
```

### 3. 使用指南
1. 打开浏览器访问 [http://localhost:8000](http://localhost:8000)。
2. **创建 Notebook**：在左侧栏点击“创建”，输入名称（如 "My Project"）。
3. **摄取资料**：
   - 粘贴 PDF 绝对路径或网页 URL。
   - 点击“开始摄取”，等待进度完成。
4. **提问**：在右侧输入问题，系统将基于当前 Notebook 的资料进行回答。
5. **管理资料**：在“已摄取资料”列表中，可以随时禁用或删除不想参与检索的文件。

## 目录结构
```
app/
  main.py        # FastAPI 入口与路由
  notebooks.py   # Notebook 目录与元数据管理
  sources.py     # 源文件聚合与状态管理
  ingest.py      # 资料解析、爬虫与分块逻辑
  hybrid.py      # 混合检索算法实现
  rag.py         # LLM 调用与答案合成
  static/
    index.html   # 前端单页应用 (SPA)
data/
  notebooks.json       # Notebook 列表元数据
  notebooks/
    {uuid}/
      chunks.json      # 分块数据存储
```

## 技术栈
- **后端**: Python, FastAPI, Uvicorn
- **爬虫**: Requests, Pyppeteer, BeautifulSoup4, Readability
- **NLP**: Jieba, Rank-BM25
- **存储**: 本地 JSON 文件系统 (无数据库依赖)

## 许可证
MIT
