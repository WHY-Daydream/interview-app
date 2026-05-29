# 每日学习笔记 → 岗位面试题生成器

将每日学习笔记通过 AI 智能转化为**岗位定制面试题**，支持流式实时生成 + 自测题库，数据仅保存在本地。

## 功能特性

- **流式生成** — 6 步流水线实时输出，内容逐字出现，像聊天一样
- **岗位匹配** — 指定目标岗位，AI 针对性出题，支持 11+ 预设岗位
- **自动重试** — 流式连接中断时自动重试（最多 3 次），从断点继续
- **面试题库** — 自动解析单道题目，支持逐题自测，标记掌握/未掌握
- **掌握统计** — 已测题数、掌握率实时统计，查漏补缺
- **题库导入** — 支持自动扫描本地 .md 文件 + Web 页面手动上传导入
- **多引擎支持** — OpenAI 兼容 API / Claude / Coze 工作流，可自由切换
- **历史记录** — 查看、重新生成、删除、导出历史面试题
- **本地存储** — SQLite 本地数据库，隐私安全

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | NiceGUI (Python Web UI) |
| AI 引擎 | OpenAI 兼容 API (DeepSeek / GPT / Claude) |
| 数据库 | SQLite + SQLAlchemy |
| HTTP | httpx / openai SDK |

## 快速开始

### 环境要求

- Python 3.10+

### 安装

```bash
cd demo

python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS / Linux

pip install -r requirements.txt
```

### 配置

编辑项目根目录 `.env` 文件：

```ini
AI_ENGINE=openai
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

APP_HOST=0.0.0.0
APP_PORT=8080
```

#### 支持的 AI 引擎

**OpenAI 兼容 API（推荐）**
```ini
AI_ENGINE=openai
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

**NVIDIA DeepSeek**
```ini
AI_ENGINE=openai
OPENAI_API_KEY=nvapi-xxx
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_MODEL=deepseek-ai/deepseek-v4-flash
```

**Claude**
```ini
AI_ENGINE=claude
CLAUDE_API_KEY=sk-ant-xxx
CLAUDE_BASE_URL=https://api.anthropic.com/v1
CLAUDE_MODEL=claude-sonnet-4-20250514
```

### 运行

```bash
python app.py
```

浏览器访问 **http://localhost:8080**

## 使用指南

### 首页 — 生成面试题

1. 填写学习日期
2. 选择目标岗位（或输入自定义岗位）
3. 粘贴每日学习笔记（Markdown 格式）
4. 点击「开始生成面试题」
5. 内容实时流式输出，6 步逐步完成

### 历史记录

- 查看所有生成记录
- 复制 / 导出 Markdown / 重新生成 / 删除

### 题库 — 自测模式

1. 点击「题库」Tab
2. 选择一套已生成的面试题（或点击上传按钮导入 .md 文件）
3. 左侧题目列表，右侧自测区域
4. 逐题查看题目 → 点击「查看答案」→ 标记「已掌握」或「未掌握」
5. 使用「上一题 / 下一题」按钮导航，底部实时显示掌握率

### 题库导入

支持两种方式将外部面试题导入系统：

**方式一：自动扫描（推荐）**

将面试题 `.md` 文件放到项目根目录，文件名格式：

```
面试题_YYYY-MM-DD_岗位名称.md
```

例如：`面试题_2026-05-22_AI大模型开发工程师.md`

应用启动时自动扫描并导入，已导入的文件不会重复导入。

**方式二：Web 页面上传**

在题库页面右上角点击上传按钮，选择 `.md` 文件即可导入。

#### 导入文件格式要求

文件内容需包含用 `**Q1: 题目**` 或 `### Q1. 题目` 标记的面试题，支持以下字段：

```markdown
**Q1: 请解释 Transformer 的自注意力机制？**
**难度**: 中
**关联知识点**: Transformer、Attention、Self-Attention
**答案**:
自注意力机制允许序列中的每个位置...
```

## 生成流水线

```
1. 笔记整理   → 清洗、结构化、提取核心概念
2. 知识图谱   → 构建知识点实体与关联关系
3. 面试题生成  → 生成 8-12 道岗位相关面试题
4. 质量审查   → 修正错误、去重、补充缺失
5. 补充练习题  → 针对薄弱环节生成 3-5 道进阶题
6. 最终整合   → 排版为完整 Markdown 文档
```

每步流式输出，失败自动重试，前面已完成的步骤不受影响。

## 项目结构

```
├── app.py              # NiceGUI 应用入口，UI 页面（首页/历史/题库）
├── llm_client.py       # LLM 客户端（流式调用 + 6 步生成流水线）
├── coze_client.py      # Coze Workflow API 封装
├── tasks.py            # 异步任务队列，后台执行生成
├── models.py           # 数据模型 + 题目解析 + 面试题导入
├── config.py           # 配置管理（环境变量）
├── requirements.txt    # Python 依赖
├── .env                # 环境变量配置
└── data/
    └── app.db          # SQLite 数据库（自动生成）
```

## 数据库

| 表 | 说明 |
|----|------|
| `notes` | 学习笔记（日期、原始内容、岗位、状态） |
| `interview_questions` | 生成的面试题（完整 Markdown、题目数量） |
| `quiz_records` | 自测记录（题目序号、掌握状态） |

## 配置参考

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `AI_ENGINE` | `openai` | AI 引擎：`openai` / `claude` / `coze` |
| `OPENAI_API_KEY` | `""` | OpenAI 兼容 API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API 地址 |
| `OPENAI_MODEL` | `gpt-4o` | 模型名称 |
| `CLAUDE_API_KEY` | `""` | Claude API Key |
| `CLAUDE_BASE_URL` | `https://api.anthropic.com/v1` | Claude API 地址 |
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Claude 模型 |
| `COZE_API_KEY` | `""` | Coze API Key |
| `COZE_API_URL` | `https://api.coze.cn/v1/workflow/run` | Coze API 地址 |
| `WORKFLOW_ID` | `""` | Coze 工作流 ID |
| `APP_HOST` | `0.0.0.0` | 监听地址 |
| `APP_PORT` | `8080` | 监听端口 |
| `TASK_TIMEOUT` | `300` | 生成超时（秒） |

## 常见问题

**Q: 504 Gateway Timeout？**

笔记内容过长。系统会自动截断超过 30000 字符的输入，也可在 `.env` 中调大 `TASK_TIMEOUT`。

**Q: 流式输出中断？**

网络波动导致流式连接断开。系统会自动重试当前步骤（最多 3 次），从断点继续输出。

**Q: 如何切换 AI 引擎？**

修改 `.env` 中的 `AI_ENGINE` 值（`openai` / `claude` / `coze`），并配置对应的 API Key 和地址，重启应用即可。

**Q: 导入的文件提示"已有相同记录"？**

系统按日期 + 岗位去重，避免重复导入。如需重新导入，请先在历史记录中删除已有记录。

**Q: 题库自测记录存储在哪里？**

SQLite 数据库 `data/app.db` 的 `quiz_records` 表中，删除该表即可清空所有自测记录。

## 许可证

MIT
