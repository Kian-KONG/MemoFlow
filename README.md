# MemoFlow —— 本地部署的 AI 会议助手

MemoFlow 是一个 AI 会议助手：上传会议录音，自动完成 **语音转写 → 说话人识别 → 摘要生成 → 决策 / 行动项提取 → 知识库检索（RAG）**。ASR 在本地运行（Mac 默认 MOSS MLX ~1.8GB），摘要 / Embedding / Rerank 通过云端 API 完成。

## 技术栈

| 层次 | 选型 |
|---|---|
| 后端 | FastAPI（Python） |
| 前端 | React + TypeScript（Vite） |
| 关系数据 | SQLite（SQLAlchemy 2.0 异步） |
| 向量数据 | LanceDB（嵌入式，无需单独部署） |
| 语音识别 + 说话人分离 | MOSS-Transcribe-Diarize（Mac 默认 MLX，~1.8GB）或 VibeVoice-ASR |
| 摘要 / 决策 / 行动项 | DeepSeek API（`deepseek-v4-pro`）或 Bosch AIGC 网关 |
| 知识库向量化 | OpenAI Embedding / Bosch `text-embedding-v3` |
| 检索重排 | Qwen3 Reranker（DashScope 兼容 / Bosch 网关） |

## 架构：DDD + Service Layer + 端口适配器

```
接口层 (Interfaces)      FastAPI Routes + React SPA
        │  只依赖应用服务，不直接访问仓储或领域对象
应用层 (Application)      Service Layer：用例编排、事务边界（UnitOfWork）、DTO
        │  依赖领域层 + 抽象端口（Port），不依赖具体基础设施
领域层 (Domain)           聚合根 / 实体 / 值对象 / 领域事件 / 领域服务（零 I/O 依赖）
        ▲  依赖倒置：领域层定义仓储接口，基础设施层实现
基础设施层 (Infrastructure) SQLAlchemy 仓储 / LanceDB / VibeVoice / DeepSeek / OpenAI / Qwen3 Reranker / 本地文件存储
```

**四个限界上下文（Bounded Context）**：`meeting`（会议生命周期与状态机）、`transcript`（转写与说话人）、`summary`（摘要/决策/行动项）、`knowledge`（知识库向量检索）。

**模块可替换**：所有 AI 能力与存储都通过 `application/ports/*` 定义的抽象接口访问：
- 想换成 Whisper？实现 `ASRPort` 即可。
- 想换成其他 LLM（本地 llama.cpp / 云端 API）？实现 `LLMPort` 即可。
- 想把 LanceDB 换成 Qdrant/pgvector？实现 `VectorRepository` 即可。
- 想把 SQLite 换成 PostgreSQL？实现 `UnitOfWork` + 三个仓储接口即可，应用层/领域层代码零改动。

具体装配全部集中在唯一的组合根 [src/memoflow/container.py](src/memoflow/container.py)。

## 目录结构

```
MemoFlow/
├── pyproject.toml
├── .env.example
├── frontend/                      # React + TypeScript（Vite）
│   ├── src/
│   │   ├── api/                   # REST 客户端
│   │   ├── components/
│   │   └── pages/
│   └── dist/                      # npm run build 产物（由后端托管）
├── data/                          # 运行时数据（音频、SQLite、LanceDB），已加入 .gitignore
├── src/memoflow/
│   ├── main.py                    # FastAPI 入口（CORS + 静态 SPA）
│   ├── config.py                  # Settings（pydantic-settings）
│   ├── container.py               # 组合根：依赖注入装配
│   │
│   ├── domain/                    # ── 领域层（零基础设施依赖）──
│   ├── application/               # ── 应用层（Service Layer）──
│   ├── infrastructure/            # ── 基础设施层（可替换适配器）──
│   └── interfaces/
│       └── api/                   # FastAPI 路由 + Pydantic Schema
│
└── tests/
    ├── unit/domain/
    └── integration/
```

## 快速开始

```bash
# 1. 创建虚拟环境并安装后端依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. 复制环境变量配置
cp .env.example .env
# 按需修改 .env：填入 Bosch AIGC 或 DeepSeek / OpenAI / Rerank API 密钥等

# 3. 安装并构建前端
cd frontend
npm install
npm run build
cd ..

# 4. 启动（一体：后端托管 frontend/dist）
PYTHONPATH=src uvicorn memoflow.main:app --reload --host 127.0.0.1 --port 8000
```

打开浏览器访问 `http://127.0.0.1:8000/` 使用 React 界面上传录音；
或访问 `http://127.0.0.1:8000/docs` 查看 FastAPI 自动生成的 API 文档。

### 开发模式（前后端分端口）

```bash
# 终端 1 — 后端
PYTHONPATH=src uvicorn memoflow.main:app --reload --host 127.0.0.1 --port 8000

# 终端 2 — 前端（Vite 将 /api 代理到 :8000）
cd frontend && npm run dev
```

访问 `http://127.0.0.1:5173/`。

### 本地冒烟测试

不经过 Cloudflare，先确认后端与 API 正常：

```bash
# 终端 1：启动后端（需已 npm run build）
PYTHONPATH=src uvicorn memoflow.main:app --host 127.0.0.1 --port 8000

# 终端 2：运行检查
chmod +x ./scripts/smoke_test.sh
./scripts/smoke_test.sh
# 或指定地址: ./scripts/smoke_test.sh http://127.0.0.1:8000
```

通过 Cloudflare 隧道后，用公网 URL 再测一遍：

```bash
./scripts/smoke_test.sh https://xxxx.trycloudflare.com
```

若 `smoke_test` 失败，页面上的错误提示会说明是 502 / 网络断开还是 API 异常。

### 临时给其他设备访问（Cloudflare Quick Tunnel）

先构建前端，再启动隧道（脚本会检查 `frontend/dist`）：

```bash
cd frontend && npm run build && cd ..
brew install cloudflared
chmod +x ./scripts/start_with_cloudflare_tunnel.sh
./scripts/start_with_cloudflare_tunnel.sh
```

终端会输出 `https://xxxx.trycloudflare.com`，在另一台电脑的浏览器打开即可。计算和模型仍在本机运行；关闭脚本后外网链接失效。

**注意：** Quick Tunnel 单次请求超时约 100 秒。大会议录音（尤其 &gt;30MB）经隧道上传可能返回 **524**（Cloudflare 超时，页面显示 HTML 错误）。大文件请在本机 `http://127.0.0.1:8000` 上传，或先压缩/切分音频。

### 首次使用需要准备

- **ASR 模型**（本地权重）：
  ```bash
  pip install -U "huggingface_hub[cli]"
  pip install -e ".[moss-asr]"    # Mac 使用 MOSS 转写时需要
  chmod +x ./scripts/download_asr_model.sh
  ./scripts/download_asr_model.sh   # Mac 默认下载 MOSS MLX (~1.8GB)
  ```
  下载脚本**默认从 ModelScope 拉取**（国内推荐，支持断点续传）。`moss_hf` 与 `vibevoice` 分别对应 ModelScope 仓库 `OpenMOSS/MOSS-Transcribe-Diarize`、`microsoft/VibeVoice-ASR-HF`。若需改回 HuggingFace，可设 `USE_MODELSCOPE=0`。

  **`mlx_moss` 例外**：ModelScope 暂无 MLX 转换版，Mac 默认后端仍经 HF 镜像（`hf-mirror`）下载 `vanch007/mlx-MOSS-Transcribe-Diarize`。

  确保 `.env` 中 `MEMOFLOW_ASR_MODEL_PATH` 与下载目录一致。

  可选后端（`.env` 中 `MEMOFLOW_ASR_BACKEND`）：
  - `mlx_moss` — `vanch007/mlx-MOSS-Transcribe-Diarize`（Mac M 系列推荐，HF 镜像）
  - `moss_hf` — `OpenMOSS/MOSS-Transcribe-Diarize`（ModelScope）
  - `vibevoice` — `microsoft/VibeVoice-ASR-HF`（ModelScope，~16.7GB）
- **Bosch AIGC（推荐）**：在 `.env` 中配置 `BOSCH_AIGC_API_KEY`、`LLM_API_URL`、`EMBEDDING_API_URL`、`RERANKER_API_URL`。
- 或分别配置 DeepSeek / OpenAI Embedding / Qwen3 Reranker 的 `MEMOFLOW_*` 密钥。

## 运行测试

```bash
pip install -e ".[dev]"
pytest tests/unit          # 纯领域逻辑测试，秒级完成
pytest tests/integration   # 使用假 AI 适配器的端到端流水线测试
```

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/meetings` | 上传会议录音，创建会议并异步触发处理流水线 |
| GET | `/api/meetings` | 会议列表（支持按状态过滤、分页） |
| GET | `/api/meetings/{id}` | 会议详情 |
| POST | `/api/meetings/{id}/retry` | 重试失败的处理流水线 |
| GET | `/api/meetings/{id}/transcript` | 获取转写结果（含说话人标注） |
| GET | `/api/meetings/{id}/summary` | 获取摘要、决策、行动项 |
| POST | `/api/knowledge/search` | 知识库语义检索（可指定 meeting_id 限定范围） |
| GET | `/api/system/status` | 系统依赖与模型就绪状态 |
| GET | `/health` | 健康检查 |

## 会议处理状态机

```
UPLOADED → TRANSCRIBING → DIARIZING → SUMMARIZING → COMPLETED
              │                │            │
              └────────────────┴────────────┴──→ FAILED（可 retry 回到 TRANSCRIBING）
```
