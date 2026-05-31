# 教训记录 & 后续方案

## 教训 1：`_regenerate_from_note` 强制切换 tab 破坏用户位置

**错误：**
`_regenerate_from_note()` 中调用了 `_NAV_TABS.set_value("首页")`，强制把用户从「历史记录」tab 切到「首页」。用户如果不想看生成进度，只想在历史页面等，会被打断。

**根因：**
我没有站在用户视角思考——用户点击「重新生成」后，可能希望留在历史页面观察新记录出现，而不是被踢走。

**修复方向：**
- 保留切换 tab 的功能（因为生成进度在首页展示，用户需要看到），但要配合 tab 持久化
- 如果用户不希望被切换，可以通过 tab 持久化记住用户最终位置

---

## 教训 2：页面刷新后 tab 不持久

**错误：**
`ui.tab_panels(tabs, value="首页")` 写死了默认值。用户刷新页面后，所有 JS 状态丢失，永远回到「首页」tab。用户如果正在浏览历史记录，刷新后找不到位置了。

**根因：**
没有使用 NiceGUI 的 `app.storage.user` 来持久化 UI 状态。这是一个基础的前端状态管理缺失。

**另一个错误（运行时崩溃）：**
只用 `app.storage.user` 而不在 `ui.run()` 中传 `storage_secret`，会抛 `RuntimeError` 导致页面 500。**修了代码没测试运行就上线了**。

**修复方向：**
- 在 `ui.run()` 中加入 `storage_secret=settings.STORAGE_SECRET`
- 在 config.py 中新增 `STORAGE_SECRET` 配置项（环境变量可覆盖）
- 在 `main_page()` 中从 `app.storage.user` 恢复 tab 状态
- 在 tab 切换时保存状态到 `app.storage.user`
- 这样无论用户怎么刷新，都能回到上次所在的 tab

---

## 教训 3：Step 6「最终整合」`max_tokens=16000` 导致 API 超时死循环

**错误：**
Step 6 `max_tokens=16000` 请求输出量太大，NVIDIA API 网关 5 分钟超时（`API_TIMEOUT=300`）。OpenAI SDK 内置 `max_retries=2` 自动重试，每重试一次又等 5 分钟，陷入「超时→重试→再超时」的死循环。用户看到的就是「一直没反应」。

时间线证据：
| 事件 | 时间 | 耗时 |
|---|---|---|
| Step 5（扩展追问）结束 | 17:33:57 | 6 秒 |
| Step 6（最终整合）开始 | 17:48:11 | — |
| 首次超时 + SDK 重试 | 17:53:12 | ~5 分钟 |

**根因：**
1. **`max_tokens=16000` 设定不合理** — 最终整合只是排版，6000-8000 tokens 足够
2. **Step 6 直接调 `client.chat()` 不走 `_call()` 函数** — 非流式模式下 `_call()` 有 try/except 处理，但 Step 6 独立编写了逻辑，没有复用 `_call()` 的重试能力
3. **非流式模式放大超时问题** — 流式模式下即使超时，已生成内容会逐块返回，不会全部丢失
4. **没有设置合理的 max_tokens 上限** — 其它步骤都是 4000-8000，唯独 Step 6 设了 16000

**修复方向：**
- 将 Step 6 的 `max_tokens` 从 16000 降到 8000
- 让 Step 6 也走 `_call()` 获取统一的重试和流式处理
- 长期：对所有步骤的 `max_tokens` 设置上限，防止 API 超时

## 教训 4：`ui.timer()` 作为轮询方案的 parent slot 崩溃

**错误现象：**
日志每秒出现 `RuntimeError: The parent slot of the element has been deleted.`，应用无明显表现异常但日志大量刷错。

**根因分析（两层）：**

**第一层（NiceGUI timer.py 源码缺陷，v2.11.x）：**
- `ui.timer()` 本质上是一个 UI 元素（有 `parent_slot`）+ 一个后台协程
- 当元素被 NiceGUI 回收（例如页面重新构建），`_handle_delete()` 只调用 `cancel()` —— 这个 cancel 仅仅是设置 `self._is_canceled = True`
- 但后台协程 `_run_in_loop` 仍在事件循环中运行
- 下一轮 `_run_in_loop` 调用 `_get_context()` 时，访问已删除元素的 `parent_slot` → `RuntimeError`

**第二层（我们的用法缺陷）：**
- 页面刷新/重连时 `main_page()` 重新执行，创建新的 `_TIMER_ROOT`
- 但旧的 `_TIMER_ROOT` 已被事件循环标记为旧上下文，旧 timer 的协程仍引用旧元素
- 新旧混杂 → 必崩

**修复方案（三步走）：**

**第 1 步 — 劫持 timer 生命周期（临时方案，2026-05-31 实施）：**
- 在 `main_page()` 中每次重建 `_TIMER_ROOT` 前，先 `.clear()` 旧容器
- 检测到 `parent slot deleted` 错误时主动停止轮询
- 问题：仍有短暂窗口期会报错

**第 2 步 — 完全替换为 asyncio 协程（2026-06-01 实施）：**
- 移除所有 `ui.timer()` 调用
- 改为 `async def _poll_loop()` + `asyncio.create_task()`
- 旧任务直接用 `task.cancel()` 彻底停止，`asyncio.CancelledError` 在 `await` 点注入后被 except 捕获，干净退出
- 不再需要 `_TIMER_ROOT` 作为 timer 的父 slot
- `_stop_timer()` 从 `.deactivate()` 改为 `.cancel()`

**具体改动文件：** `app.py`
- 替换 task poll：`_safe_poll_task()` → `_task_poll_loop()` + `asyncio.create_task`
- 替换 KG poll：`_kg_poll_cb()` + `ui.timer()` → `_kg_poll_loop()` + `asyncio.create_task`
- 删除 `_safe_poll_task()` 包装器
- 删除 `_TIMER_ROOT` 全局引用

**验证指标：**
- `app.py` 中 `ui.timer()` 调用数：0
- `asyncio.create_task()` 调用数：2（task poll + KG poll）

**后续预防：**
- 不要在 NiceGUI 应用中使用 `ui.timer()` 做后台轮询
- 后台循环统一使用 `asyncio.create_task()`，生命周期通过 `task.cancel()` 管理
- 所有任务应有唯一 `name` 参数便于调试

---

## 后续优化思路

### 1. Tab 持久化（本次修复）

使用 `app.storage.user` 做三件事：
- 页面加载时从 storage 恢复 active_tab
- tab 切换时将新值写入 storage
- tab_panels 的 value 初始值从 storage 读取

### 2. 生成完成后的智能跳转

用户点了「重新生成」后，自动切换到首页看进度是合理的。但生成完成后，可以：
- 在通知里加链接「点击查看历史记录」
- 或者直接刷新历史列表，让用户看到新记录

### 3. 历史页面「查看」已生成内容后不要打断浏览

当前查看对话框是 modal，关闭后用户仍在历史页面。这没问题，但：
- 如果用户查看了「处理中」的记录，对话框提示「请稍后刷新查看」
- 刷新后回到首页 → 就是本次要修的 bug

### 4. 更通用的状态持久化框架

未来可以推广到：
- 题库页面的筛选条件
- 知识图谱的展开状态
- 主题/暗色模式（已有）
