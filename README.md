# MemoFlow —— 本地部署的 AI 会议助手

MemoFlow 是一个完全本地运行的 AI 会议助手：上传会议录音，自动完成 **语音转写 → 说话人识别 → 摘要生成 → 决策 / 行动项提取 → 知识库检索（RAG）**，无需将录音上传到任何云端服务。

## 技术栈

| 层次 | 选型 |
|---|---|
| Web / UI | FastAPI + NiceGUI |
| 关系数据 | SQLite（SQLAlchemy 2.0 异步） |
| 向量数据 | LanceDB（嵌入式，无需单独部署） |
| 语音识别 (ASR) | SenseVoice-Small（通过 FunASR） |
| 说话人识别 | pyannote.audio (`speaker-diarization-3.1`) |
| 摘要 / 决策 / 行动项 | Qwen3-14B，通过 MLX 在 Apple Silicon 上本地推理 |
| 知识库向量化 | sentence-transformers（如 BAAI/bge-small-zh-v1.5） |

## 架构：DDD + Service Layer + 端口适配器

```
接口层 (Interfaces)      FastAPI Routes / NiceGUI Pages
        │  只依赖应用服务，不直接访问仓储或领域对象
应用层 (Application)      Service Layer：用例编排、事务边界（UnitOfWork）、DTO
        │  依赖领域层 + 抽象端口（Port），不依赖具体基础设施
领域层 (Domain)           聚合根 / 实体 / 值对象 / 领域事件 / 领域服务（零 I/O 依赖）
        ▲  依赖倒置：领域层定义仓储接口，基础设施层实现
基础设施层 (Infrastructure) SQLAlchemy 仓储 / LanceDB / SenseVoice / pyannote / Qwen3-MLX / 本地文件存储
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
├── data/                          # 运行时数据（音频、SQLite、LanceDB），已加入 .gitignore
├── src/memoflow/
│   ├── main.py                    # FastAPI + NiceGUI 应用入口
│   ├── config.py                  # Settings（pydantic-settings）
│   ├── container.py               # 组合根：依赖注入装配
│   │
│   ├── domain/                    # ── 领域层（零基础设施依赖）──
│   │   ├── shared/                # Entity/AggregateRoot/ValueObject/DomainEvent 基类、异常
│   │   ├── meeting/                # Meeting 聚合根、状态机、AudioValidationPolicy
│   │   ├── transcript/             # Transcript/Utterance/Speaker 聚合、话语-说话人对齐算法
│   │   ├── summary/                # Summary/Decision/ActionItem 聚合
│   │   └── knowledge/              # KnowledgeChunk 聚合、Embedding 值对象
│   │
│   ├── application/                # ── 应用层（Service Layer）──
│   │   ├── ports/                  # ASR/Diarization/LLM/Embedding/FileStorage/UnitOfWork 抽象端口
│   │   ├── dto.py                  # 应用层 DTO
│   │   ├── meeting_service.py      # 上传会议、查询、重试
│   │   ├── transcription_service.py# 编排 ASR + 说话人识别 + 转写组装
│   │   ├── summary_service.py      # 编排 LLM 生成摘要/决策/行动项
│   │   ├── knowledge_service.py    # 切片、向量化、索引、语义检索
│   │   └── pipeline/               # 流水线编排 + 后台任务调度
│   │
│   ├── infrastructure/             # ── 基础设施层（可替换适配器）──
│   │   ├── persistence/            # SQLAlchemy ORM 模型、仓储实现、UnitOfWork 实现
│   │   ├── vectorstore/            # LanceDB 向量仓储实现
│   │   ├── ai/                     # SenseVoice / pyannote / Qwen3-MLX / Embedding 适配器
│   │   └── storage/                # 本地文件存储
│   │
│   └── interfaces/                 # ── 接口层 ──
│       ├── api/                    # FastAPI 路由 + Pydantic Schema
│       └── ui/                     # NiceGUI 页面
│
└── tests/
    ├── unit/domain/                # 纯领域逻辑单元测试（无需任何基础设施）
    └── integration/                # 使用假 AI 适配器驱动完整流水线的集成测试
```

## 快速开始

```bash
# 1. 创建虚拟环境并安装依赖（首次运行建议先只装非 AI 依赖以验证骨架，再按需装 AI 依赖）
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. 复制环境变量配置
cp .env.example .env
# 按需修改 .env：填入 HuggingFace token（pyannote 需要）、选择设备（cpu/mps）等

# 3. 启动开发服务器
uvicorn memoflow.main:app --reload --host 127.0.0.1 --port 8000
```

打开浏览器访问 `http://127.0.0.1:8000/` 使用 NiceGUI 界面上传录音；
或访问 `http://127.0.0.1:8000/docs` 查看 FastAPI 自动生成的 API 文档。

### 首次使用需要准备的模型

- **SenseVoice**：首次调用会自动从 ModelScope/HuggingFace 下载 `iic/SenseVoiceSmall`。
- **pyannote**：需要在 https://huggingface.co/pyannote/speaker-diarization-3.1 接受协议，并在 `.env` 中配置 `MEMOFLOW_HF_TOKEN`。
- **Qwen3-14B (MLX)**：建议使用 `mlx-community` 提供的量化版本（如 `mlx-community/Qwen3-14B-4bit`），首次运行会自动下载。
- **Embedding**：`BAAI/bge-small-zh-v1.5` 等 sentence-transformers 模型会自动下载。

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
| GET | `/health` | 健康检查 |

## 会议处理状态机

```
UPLOADED → TRANSCRIBING → DIARIZING → SUMMARIZING → COMPLETED
              │                │            │
              └────────────────┴────────────┴──→ FAILED（可 retry 回到 TRANSCRIBING）
```
