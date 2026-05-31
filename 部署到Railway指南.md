# 🚀 部署到 Railway 操作指南

## 项目概况

这是一个 Python NiceGUI 应用（每日学习笔记 → 岗位面试题生成器），使用 SQLite 作为本地数据库，支持 OpenAI/Claude/Coze 三种 AI 引擎。

---

## 前提条件

- 拥有 [GitHub](https://github.com) 账号
- 拥有 [Railway](https://railway.app) 账号（可用 GitHub 登录）
- 可用且余额充足的 API Key（OpenAI / DeepSeek / Claude / Coze 任选其一）

---

## 操作步骤

### Step 1：推送到 GitHub 仓库

```bash
# 在项目根目录执行
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin master
```

> `.gitignore` 已排除 `.env`、`data/`、`__pycache__/` 等，这些不会提交到 Git。

### Step 2：在 Railway 创建项目

1. 登录 [railway.app](https://railway.app)（推荐直接用 GitHub 账号登录）
2. 点击 **New Project** → **Deploy from GitHub repo**
3. 选择你刚才推送的仓库
4. Railway 会自动检测到这是一个 Python 项目（依据 `requirements.txt` + `Procfile`），自动执行：
   - `pip install -r requirements.txt`
   - `python app.py`（由 `Procfile` 中 `web: python app.py` 指定）

### Step 3：配置环境变量

在 Railway Dashboard 中，进入项目 → **Variables** 标签页，添加以下变量：

| 变量名 | 必填 | 说明 | 示例值 |
|--------|------|------|--------|
| `AI_ENGINE` | ✅ | AI 引擎类型 | `openai` / `claude` / `coze` |
| `OPENAI_API_KEY` | ① | API Key | `sk-xxx...` |
| `OPENAI_BASE_URL` | ① | API 地址 | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | ① | 模型名称 | `gpt-4o` / `deepseek-chat` |
| `CLAUDE_API_KEY` | ② | Claude API Key | `sk-ant-xxx...` |
| `COZE_API_KEY` | ③ | Coze API Key | `pat_xxx...` |
| `COZE_WORKFLOW_ID` | ③ | Coze 工作流 ID | `xxx` |
| `STORAGE_SECRET` | ✅ | 会话加密密钥 | 任意长随机字符串（建议 32 位以上） |
| `APP_HOST` | ❌ | 监听地址（Railway 默认 0.0.0.0） | 不填即可 |
| `APP_PORT` | ❌ | ⚠️ 见下方"已知问题" | 不填即可 |

> ① 当 `AI_ENGINE=openai` 时必填
> ② 当 `AI_ENGINE=claude` 时必填
> ③ 当 `AI_ENGINE=coze` 时必填

### Step 4：查看部署日志

1. 在 Railway Dashboard 中点击 **Deployments**
2. 点击当前部署查看实时构建和运行日志
3. 如果失败，日志中会显示具体错误原因
4. 部署成功后，Railway 会自动分配一个 `*.railway.app` 域名

### Step 5：访问应用

直接打开 Railway 分配的域名即可访问。例如：`https://your-project.up.railway.app`

---

## ⚠️ 已知问题 — 需要改代码

### 问题 1：端口绑定不匹配

**原因**：Railway 通过环境变量 `PORT` 动态分配端口，但应用读取的是 `APP_PORT`（默认 8080）。两者不匹配导致应用绑定到 8080，而 Railway 负载均衡器在等待 `$PORT`，最终超时 502/504。

**修复**：修改 `config.py`，增加 Railway `PORT` 变量回退逻辑：

```python
# 原代码
APP_PORT: int = int(os.getenv("APP_PORT", 8080))

# 改为
APP_PORT: int = int(os.getenv("APP_PORT", os.getenv("PORT", 8080)))
```

**效果**：优先读 `APP_PORT`，没有则读 Railway 分配的 `PORT`，都没有则回退 8080。

### 问题 2：SQLite 数据不持久

**原因**：Railway 的文件系统是**临时**的。每次部署重启后 `data/app.db` 都会消失，所有面试题和自测记录丢失。

**可选方案**：

| 方案 | 说明 | 难度 | 费用 |
|------|------|------|------|
| **接受不持久** | 不处理，每次重启后重新生成 | 无 | 免费 |
| **Railway Volume** | 挂载持久化存储到 `data/` 目录 | 低 | Railway 付费 |
| **外部数据库** | 改用 PostgreSQL（Railway 提供） | 中 | 免费额度够用 |

选择"接受不持久"不必改代码。如果选择 PostgreSQL，需要修改 `models.py` 数据库连接字符串：

```python
# 在 models.py 中增加环境变量判断
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/app.db")

if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
```

---

## 快速修复清单

| # | 操作 | 必须 | 状态 |
|---|------|------|------|
| 1 | 推代码到 GitHub | ✅ 是 | 未完成 |
| 2 | Railway 绑定 GitHub 仓库 | ✅ 是 | 未完成 |
| 3 | 设置环境变量 (API Key 等) | ✅ 是 | 未完成 |
| 4 | 修 `config.py` 端口回退 | ✅ 是，否则无法启动 | 未完成 |
| 5 | 决策 SQLite 数据方案 | ❌ 否，接受丢失可不改 | 待定 |

---

## 疑难排查

### 构建成功但访问显示 502/504

大概率是端口问题。请确认：
1. 是否已修改 `config.py` 中的 `APP_PORT` 回退逻辑
2. 查看 Railway 日志中应用实际绑定的端口号
3. 检查 `APP_HOST` 是否为 `0.0.0.0`（默认值）

### 构建失败：找不到依赖

```bash
# 可以在 Railway 的构建日志中看到具体报错
# 常见原因：requirements.txt 中版本号不兼容
# 解决方法：在本地重新测试安装
pip install -r requirements.txt
```

### 应用能启动但 AI 生成失败

检查环境变量中 API Key 是否正确设置。Railway 的环境变量是部署级别的 —— 修改后需要重新部署才能生效。

### 部署后所有数据都消失了

这是 SQLite 临时存储导致的正常现象。参考"问题 2"选择持久化方案。

---

## 参考链接

- [Railway 官方文档 - Python 部署](https://docs.railway.app/guides/python)
- [Railway 环境变量](https://docs.railway.app/guides/variables)
- [Railway 持久化 Volume](https://docs.railway.app/guides/volumes)
