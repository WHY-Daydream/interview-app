"""📚 每日学习笔记 → 岗位面试题生成器 — NiceGUI 主应用"""

import json
import logging
import os
import sys
from pathlib import Path
from datetime import date as date_today
from typing import Optional

# ── 编码修复（Windows GBK 兼容） ──
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

from nicegui import app, ui

from config import settings
from models import get_all_notes, get_notes_cached, invalidate_notes_cache, get_note_by_id, get_questions_by_note_id, delete_note, parse_questions, save_quiz_record, get_quiz_records, reset_quiz_records, import_questions_from_markdown, get_knowledge_graph, save_knowledge_graph
from tasks import GenerateTask, get_all_tasks, get_task, start_generate_task

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── 全局状态 ──
CURRENT_TASK_ID: Optional[str] = None
CURRENT_TIMER = None  # 当前轮询定时器
JOB_POSITIONS = [
    "AI大模型开发工程师",
    "Java 后端开发",
    "前端开发工程师",
    "全栈开发工程师",
    "算法工程师",
    "数据分析师",
    "Linux C/C++ 嵌入式开发",
    "测试开发工程师",
    "运维工程师",
    "考研（计算机/数学）",
    "产品经理",
    "自定义岗位",
]

# ══════════════════════════════════════════════════
# 全局 CSS — 自定义现代化主题
# ══════════════════════════════════════════════════

def inject_global_styles():
    """注入全局 CSS — 清爽笔记风格"""
    ui.add_head_html("""
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
      /* ════════════════════════════════════════════
         设计系统 · 清新蓝调
         ════════════════════════════════════════════ */
      :root {
        --accent: #2563eb;
        --accent-light: #60a5fa;
        --accent-lighter: #93c5fd;
        --accent-subtle: #eff6ff;
        --accent-dark: #1d4ed8;
        --rose: #e11d48;
        --green: #059669;
        --amber: #d97706;

        --surface: #ffffff;
        --surface-alt: #f8fafc;
        --surface-card: #ffffff;
        --surface-hover: #f1f5f9;
        --border: #e2e8f0;
        --border-light: #f1f5f9;
        --divider: #eaeef5;

        --text: #0b1a33;
        --text-secondary: #475569;
        --text-muted: #94a3b8;
        --text-inverse: #ffffff;

        --radius: 12px;
        --radius-sm: 8px;
        --radius-lg: 16px;

        --shadow-sm: 0 1px 2px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.03);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.03);
        --shadow-lg: 0 12px 32px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04);
        --shadow-xl: 0 24px 48px rgba(0,0,0,0.07);

        --transition: all 0.2s ease;

        --page-bg: #f6f8fc;
      }

      body.dark {
        --accent: #60a5fa;
        --accent-light: #93c5fd;
        --accent-lighter: #bfdbfe;
        --accent-subtle: #1e3a5f;
        --accent-dark: #3b82f6;
        --surface: #0f172a;
        --surface-alt: #020617;
        --surface-card: #1e293b;
        --surface-hover: #334155;
        --border: #334155;
        --border-light: #1e293b;
        --divider: #1e293b;
        --text: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
        --shadow-lg: 0 12px 32px rgba(0,0,0,0.5);
        --shadow-xl: 0 24px 48px rgba(0,0,0,0.6);
        --page-bg: #020617;
      }

      /* 基础重置 */
      *, *::before, *::after { box-sizing: border-box; }
      body {
        font-family: 'Inter', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
        background: var(--page-bg) !important;
        color: var(--text);
        transition: background 0.3s, color 0.3s;
        min-height: 100vh;
        line-height: 1.65;
        -webkit-font-smoothing: antialiased;
      }
      ::selection { background: var(--accent-lighter); color: var(--accent-dark); }
      ::-webkit-scrollbar { width: 5px; height: 5px; }
      ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
      ::-webkit-scrollbar-track { background: transparent; }

      /* ════════════════════════════════════════════
         导航栏 · 简洁白底
         ════════════════════════════════════════════ */
      .app-header {
        background: var(--surface) !important;
        border-bottom: 1px solid var(--border) !important;
        padding: 0 32px !important;
        height: 58px !important;
        position: sticky !important;
        top: 0;
        z-index: 100;
      }
      .app-header .q-tab {
        color: var(--text-muted) !important;
        min-height: 58px;
        padding: 0 18px;
        font-weight: 500;
        font-size: 14px;
        transition: var(--transition);
        gap: 5px;
        text-transform: none !important;
        border-radius: 0 !important;
      }
      .app-header .q-tab:hover {
        color: var(--text) !important;
        background: var(--surface-hover);
      }
      .app-header .q-tab--active {
        color: var(--accent) !important;
        font-weight: 600;
      }
      .app-header .q-tab--active::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 16px;
        right: 16px;
        height: 2.5px;
        background: var(--accent);
        border-radius: 3px 3px 0 0;
      }
      .app-header .q-tab__indicator { display: none !important; }
      .app-header .q-tab__icon { font-size: 17px; }
      .theme-toggle {
        color: var(--text-muted) !important;
        border-radius: 8px !important;
        padding: 6px 8px !important;
        transition: var(--transition);
      }
      .theme-toggle:hover { background: var(--surface-hover) !important; color: var(--text) !important; }

      /* ════════════════════════════════════════════
         页面容器
         ════════════════════════════════════════════ */
      .page-wrap {
        max-width: 960px;
        margin: 0 auto;
        padding: 28px 24px 60px;
        position: relative;
      }
      /* ════════════════════════════════════════════
         卡片
         ════════════════════════════════════════════ */
      .card-note, .card-modern {
        background: var(--surface-card) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-sm) !important;
        border: 1px solid var(--border) !important;
        transition: var(--transition);
        overflow: hidden;
      }
      .card-note:hover, .card-modern:hover { box-shadow: var(--shadow-md) !important; }

      .card-note-section {
        padding: 20px 24px;
      }
      .card-note-section + .card-note-section {
        border-top: 1px solid var(--divider);
      }

      /* ════════════════════════════════════════════
         输入组件
         ════════════════════════════════════════════ */
      .input-modern .q-field__control {
        border-radius: var(--radius-sm) !important;
        background: var(--surface) !important;
        border: 1.5px solid var(--border);
        transition: var(--transition);
        min-height: 42px !important;
        box-shadow: none !important;
      }
      .input-modern .q-field__control:hover { border-color: var(--accent-light); }
      .input-modern .q-field--focused .q-field__control {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
      }
      .input-modern .q-field__label {
        color: var(--text-muted) !important;
        font-size: 13px !important;
        font-weight: 400 !important;
      }
      .input-modern textarea { line-height: 1.75 !important; }
      .input-modern .q-field__native { padding: 8px 0; }

      /* ════════════════════════════════════════════
         按钮
         ════════════════════════════════════════════ */
      .btn-primary {
        background: var(--accent) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 10px 24px !important;
        font-size: 14px !important;
        letter-spacing: 0.15px;
        transition: var(--transition);
        box-shadow: 0 4px 12px rgba(37,99,235,0.25);
        border: none !important;
        color: white !important;
        text-transform: none !important;
      }
      .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(37,99,235,0.35); }
      .btn-primary:active { transform: translateY(0); }
      .btn-primary:disabled { opacity: 0.5; transform: none !important; box-shadow: none !important; }

      .btn-ghost {
        border-radius: 10px !important;
        font-weight: 500 !important;
        padding: 8px 16px !important;
        font-size: 13px !important;
        transition: var(--transition);
        background: transparent !important;
        color: var(--text-secondary) !important;
        text-transform: none !important;
      }
      .btn-ghost:hover { background: var(--surface-hover) !important; color: var(--text) !important; }

      .btn-secondary {
        border-radius: 10px !important;
        font-weight: 500 !important;
        padding: 8px 16px !important;
        font-size: 13px !important;
        transition: var(--transition);
        border: 1.5px solid var(--border) !important;
        background: var(--surface) !important;
        color: var(--text-secondary) !important;
        text-transform: none !important;
      }
      .btn-secondary:hover { border-color: var(--accent) !important; color: var(--accent) !important; }

      /* ════════════════════════════════════════════
         进度条
         ════════════════════════════════════════════ */
      .progress-modern .q-linear-progress__track {
        background: var(--border) !important;
        border-radius: 4px !important;
        height: 6px !important;
      }
      .progress-modern .q-linear-progress__model {
        background: linear-gradient(90deg, var(--accent), var(--accent-light)) !important;
        border-radius: 4px !important;
      }

      /* ════════════════════════════════════════════
         状态标签
         ════════════════════════════════════════════ */
      .badge { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 20px; }
      .badge-done { background: #dcfce7; color: #166534; }
      .badge-failed { background: #fee2e2; color: #991b1b; }
      .badge-processing, .badge-pending { background: #fef3c7; color: #92400e; }
      body.dark .badge-done { background: #064e3b; color: #6ee7b7; }
      body.dark .badge-failed { background: #7f1d1d; color: #fca5a5; }
      body.dark .badge-processing,
      body.dark .badge-pending { background: #78350f; color: #fcd34d; }

      /* ════════════════════════════════════════════
         历史记录卡片
         ════════════════════════════════════════════ */
      .history-card {
        background: var(--surface-card) !important;
        border-radius: var(--radius) !important;
        border: 1px solid var(--border) !important;
        box-shadow: var(--shadow-sm) !important;
        transition: var(--transition);
        padding: 16px 20px !important;
      }
      .history-card:hover { border-color: var(--accent-lighter) !important; box-shadow: var(--shadow-md) !important; }

      /* ════════════════════════════════════════════
         Markdown 渲染
         ════════════════════════════════════════════ */
      .markdown-content {
        line-height: 1.8;
        color: var(--text);
      }
      .markdown-content h1 { font-size: 22px; font-weight: 700; margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 1px solid var(--divider); }
      .markdown-content h2 { font-size: 18px; font-weight: 600; margin: 24px 0 10px; }
      .markdown-content h3 { font-size: 16px; font-weight: 600; margin: 20px 0 8px; color: var(--accent); }
      .markdown-content p { margin: 8px 0; }
      .markdown-content code {
        background: var(--surface-alt);
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
      }
      .markdown-content pre {
        background: var(--surface-alt);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        padding: 16px;
        overflow-x: auto;
      }
      .markdown-content pre code { background: none; padding: 0; }
      .markdown-content blockquote {
        border-left: 3px solid var(--accent);
        padding-left: 14px;
        color: var(--text-secondary);
        margin: 12px 0;
      }
      .markdown-content strong { color: var(--text); font-weight: 600; }
      .markdown-content ul, .markdown-content ol { padding-left: 20px; line-height: 2; }
      .markdown-content hr { border: none; border-top: 1px solid var(--divider); margin: 24px 0; }

      /* ════════════════════════════════════════════
         弹窗
         ════════════════════════════════════════════ */
      .dialog-modern .q-dialog__inner { backdrop-filter: blur(4px); }
      .dialog-modern .q-card {
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-xl) !important;
        border: 1px solid var(--border) !important;
      }

      /* ════════════════════════════════════════════
         空状态
         ════════════════════════════════════════════ */
      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 60px 20px;
        color: var(--text-muted);
        gap: 8px;
      }

      /* ════════════════════════════════════════════
         Footer
         ════════════════════════════════════════════ */
      .app-footer {
        background: var(--surface) !important;
        border-top: 1px solid var(--border) !important;
        color: var(--text-muted) !important;
        font-size: 12px;
        padding: 8px 0 !important;
      }

      /* ════════════════════════════════════════════
         动画
         ════════════════════════════════════════════ */
      @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
      }
      .fade-in { animation: fadeInUp 0.35s ease-out both; }

      /* ════════════════════════════════════════════
         工具类
         ════════════════════════════════════════════ */
      .text-primary { color: var(--accent) !important; }
      .text-secondary { color: var(--text-secondary) !important; }
      .text-muted { color: var(--text-muted) !important; }

      /* ════════════════════════════════════════════
         响应式
         ════════════════════════════════════════════ */
      @media (max-width: 768px) {
        .app-header { padding: 0 12px !important; }
        .app-header .q-tab { min-height: 48px; padding: 0 10px; font-size: 12px; }
        .page-wrap { padding: 16px 12px 40px; }
      }
    </style>
    """)


# ══════════════════════════════════════════════════
# 页面组件
# ══════════════════════════════════════════════════

def create_nav_tabs() -> ui.tabs:
    """创建现代化导航标签栏"""
    with ui.header(elevated=True).classes("app-header items-center justify-between") as header:
        # 左侧品牌区
        with ui.row().classes("items-center gap-2"):
            ui.icon("auto_stories", size="24px").classes("text-primary")
            ui.label("学习笔记 → 面试题").classes("text-base font-bold tracking-wide")
            ui.label("v1.0").classes("text-xs px-2.5 py-0.5 rounded-full border text-muted")

        # 右侧导航 + 主题切换
        with ui.row().classes("gap-1 items-center"):
            with ui.tabs().classes("gap-1") as tabs:
                ui.tab("首页", icon="edit_note")
                ui.tab("历史记录", icon="history")
                ui.tab("题库", icon="quiz")
                ui.tab("知识图谱", icon="hub")

            # 主题切换
            dark = ui.dark_mode()
            theme_icon = ui.icon("dark_mode", size="22px").classes("theme-toggle cursor-pointer ml-2")

            def _toggle_theme():
                dark.toggle()
                theme_icon.name = "light_mode" if dark.value else "dark_mode"
                theme_icon.update()

            theme_icon.on("click", _toggle_theme)

    return tabs


def build_home_page():
    """构建首页 — 笔记输入 + 面试题生成"""
    ui.space().classes("h-6")

    # ── 输入表单 ──
    with ui.card().classes("card-modern w-full max-w-5xl mx-auto p-6 fade-in"):
        with ui.row().classes("w-full items-center justify-between mb-6"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("edit_note", size="28px").classes("text-primary")
                ui.label("学习笔记输入").classes("text-xl font-bold")
                ui.badge("粘贴笔记 · AI 自动生成面试题", color="primary").props("outline").classes("text-xs")
            ui.label("📊 笔记长度：0 字符").classes("text-sm text-secondary").bind_text_from(
                form_state, "notes", lambda v: f"📊 笔记长度：{len(v or '')} 字符"
            )

        # 第一行：日期 + 岗位
        with ui.row().classes("w-full gap-6 mb-5"):
            with ui.column().classes("gap-1.5"):
                ui.label("📅 学习日期").classes("text-sm font-medium text-secondary")
                ui.date(
                    value=date_today.today().isoformat(),
                    on_change=lambda e: setattr(form_state, "date", e.value),
                ).classes("w-44 input-modern").bind_value_to(form_state, "date")

            with ui.column().classes("gap-1.5 flex-1"):
                ui.label("🎯 目标岗位").classes("text-sm font-medium text-secondary")
                ui.select(
                    label="选择目标岗位",
                    options=JOB_POSITIONS,
                    value=JOB_POSITIONS[0],
                    on_change=_on_job_change,
                ).classes("w-72 input-modern").bind_value_to(form_state, "job_position")

        # 自定义岗位输入（默认隐藏）
        with ui.row().classes("w-full mb-4") as custom_row:
            ui.input(
                label="✏️ 自定义岗位名称",
                placeholder="例如：Go 后端开发工程师 / 网络安全工程师",
                on_change=lambda e: setattr(form_state, "job_position", e.value),
            ).classes("w-80 input-modern").bind_visibility_from(form_state, "show_custom_job").props('outlined dense')

        # Markdown 笔记输入
        with ui.column().classes("w-full gap-1.5"):
            ui.label("📄 Markdown 学习笔记").classes("text-sm font-medium text-secondary")
            ui.textarea(
                placeholder="粘贴你的学习笔记（Markdown 格式）...",
            ).classes("w-full h-72 font-mono text-sm input-modern leading-relaxed").bind_value_to(
                form_state, "notes"
            ).props("border")

        # 按钮行
        with ui.row().classes("w-full justify-between items-center mt-5"):
            ui.label().bind_text_from(form_state, "notes", lambda v: f"📊 笔记长度：{len(v or '')} 字符").classes(
                "text-sm text-secondary"
            )

            with ui.row().classes("gap-3"):
                ui.button("清空", icon="delete", color="grey").props("flat").classes("btn-ghost").on("click", _clear_form)
                ui.button("开始生成面试题", icon="auto_awesome", color="primary").on(
                    "click", _start_generate
                ).classes("btn-primary px-6").bind_enabled_from(form_state, "generating", lambda v: not v)

    # ── 流式生成 & 结果 ──
    with ui.card().classes("card-modern w-full max-w-5xl mx-auto p-6 fade-in").bind_visibility_from(
        form_state, "generating"
    ).style("transition: all 0.3s ease"):
        # 6 步进度指示器
        step_names = ["笔记整理", "知识图谱", "面试题生成", "质量审查", "补充练习题", "最终整合"]
        with ui.row().classes("w-full gap-2 mb-4 items-center"):
            for i, name in enumerate(step_names):
                is_active = form_state.current_step == i + 1
                is_done = form_state.current_step > i + 1
                if is_active:
                    icon_name, icon_color = "radio_button_checked", "text-primary"
                elif is_done:
                    icon_name, icon_color = "check_circle", "text-green-500"
                else:
                    icon_name, icon_color = "radio_button_unchecked", "text-muted"
                with ui.row().classes("items-center gap-1"):
                    ui.icon(icon_name, size="16px").classes(icon_color)
                    ui.label(name).classes("text-xs text-secondary" if not is_active else "text-xs font-semibold text-primary")
                if i < 5:
                    ui.icon("arrow_forward", size="12px").classes("text-muted")
        # spinner + 当前状态
        with ui.row().classes("w-full items-center gap-3 mb-4"):
            ui.spinner(size="24px").classes("text-primary")
            ui.label().bind_text_from(form_state, "step_label").classes("text-lg font-bold")

        # 流式内容区域
        streaming_md = ui.markdown().bind_content_from(form_state, "streaming_content").classes("markdown-content")

    # ── 完成后的操作区域 ──
    with ui.card().classes("card-modern w-full max-w-5xl mx-auto p-6 fade-in").bind_visibility_from(
        form_state, "show_result"
    ):
        # 结果头部
        with ui.row().classes("w-full justify-between items-center mb-4"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("check_circle", size="28px").classes("text-green-500")
                ui.label("生成完成").classes("text-xl font-bold")
            ui.label().bind_text_from(form_state, "question_count_label").classes(
                "px-3 py-1 rounded-full bg-primary/10 text-primary font-semibold text-sm"
            )

        # 操作按钮
        with ui.row().classes("w-full gap-2 mb-4 flex-wrap"):
            ui.button("去题库自测", icon="quiz", color="primary").on(
                "click", lambda: ui.notify("请切换到「题库」Tab 开始自测", type="info")
            ).classes("btn-primary")
            ui.button("📋 复制结果", icon="content_copy", color="secondary").on(
                "click", _copy_result
            ).classes("btn-secondary")
            ui.button("📥 导出 Markdown", icon="download", color="secondary").on(
                "click", _export_markdown
            ).classes("btn-secondary")
            ui.button("🔄 重新生成", icon="refresh", color="grey").on("click", _regenerate).classes("btn-ghost")


def build_history_page():
    """构建历史记录页面"""
    ui.space().classes("h-6")

    with ui.card().classes("card-modern w-full max-w-5xl mx-auto p-6 fade-in"):
        with ui.row().classes("w-full justify-between items-center mb-5"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("history", size="26px").classes("text-primary")
                ui.label("历史记录").classes("text-xl font-bold")
            ui.button("🔄 刷新", icon="refresh", on_click=_refresh_history).classes("btn-ghost")

        # 搜索 + 筛选
        with ui.row().classes("w-full gap-3 mb-4 items-center"):
            search_input = ui.input(label="搜索岗位", placeholder="输入岗位名称...").classes("flex-1").props("outlined dense clearable")
            all_positions = list(dict.fromkeys(n.job_position for n in get_notes_cached()))
            position_filter = ui.select(
                options=["全部"] + all_positions,
                value="全部",
                label="岗位筛选",
            ).classes("w-48").props("outlined dense")

        # 历史列表容器
        history_container = ui.column().classes("w-full gap-3")

        def render_history():
            history_container.clear()
            with history_container:
                notes = get_notes_cached(limit=50)

                # 应用筛选
                keyword = (search_input.value or "").strip()
                pos = position_filter.value
                if keyword:
                    notes = [n for n in notes if keyword.lower() in n.job_position.lower()]
                if pos and pos != "全部":
                    notes = [n for n in notes if n.job_position == pos]

                if not notes:
                    with ui.column().classes("empty-state"):
                        ui.icon("menu_book", size="56px").classes("opacity-30")
                        ui.label("暂无历史记录").classes("text-lg font-medium mt-2")
                        if keyword or (pos and pos != "全部"):
                            ui.label("没有匹配的记录，试试别的关键词").classes("text-sm text-muted mt-1")
                        else:
                            ui.label("先生成一份面试题吧！").classes("text-sm text-muted mt-1")
                    return

                for note in notes:
                    status_style = {
                        "done": ("badge-done", "✅", "已完成"),
                        "failed": ("badge-failed", "❌", "失败"),
                        "processing": ("badge-processing", "⏳", "处理中"),
                        "pending": ("badge-pending", "⏳", "排队中"),
                    }.get(note.status, ("badge-pending", "❓", "未知"))
                    badge_cls, icon, status_text = status_style

                    with ui.card().classes("history-card w-full p-4"):
                        with ui.row().classes("w-full justify-between items-center"):
                            with ui.column().classes("gap-1.5"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(f"{icon} {note.date}").classes("text-base font-bold")
                                    ui.html(f"<span class='badge {badge_cls}'>{status_text}</span>")
                                with ui.row().classes("items-center gap-3"):
                                    ui.label(f"💼 {note.job_position}").classes(
                                        "text-sm px-2 py-0.5 rounded-md bg-primary/5 text-primary"
                                    )
                                    ui.label(f"📄 {len(note.raw_notes)} 字").classes("text-sm text-muted")
                                    if hasattr(note, 'questions') and note.questions:
                                        q = note.questions[0]
                                        ui.label(f"📝 {q.question_count} 题").classes("text-sm text-muted")

                            with ui.row().classes("gap-2"):
                                if note.status == "done":
                                    ui.button("查看", icon="visibility", color="primary").props(
                                        "dense flat"
                                    ).classes("btn-ghost text-primary").on("click", lambda n=note: _view_history(n))
                                ui.button("删除", icon="delete", color="negative").props(
                                    "dense flat"
                                ).classes("btn-ghost text-negative").on("click", lambda n=note: _confirm_delete(n))

        # 筛选变化时重新渲染
        search_input.on("update:model-value", lambda e: render_history())
        position_filter.on("update:model-value", lambda e: render_history())
        render_history()


KG_PAGE_CSS = """
.kg-node-tooltip { font-size: 13px; }
.kg-weak-card {
    background: var(--surface-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 12px 16px;
    transition: var(--transition);
}
.kg-weak-card:hover { border-color: var(--accent-light); box-shadow: var(--shadow-sm); }
"""


class KgState:
    """知识图谱页面状态"""
    def __init__(self):
        self.notes_list: list = []
        self.current_note_id: Optional[int] = None
        self.graph_data: Optional[dict] = None  # 解析后的 JSON
        self.weak_areas: list = []
        self.knowledge_points: list = []
        self.relationships: list = []
        self.questions: list[dict] = []  # 解析后的面试题
        self.generating: bool = False
        self.gen_start_time: float = 0  # 生成开始时间
        self.gen_elapsed: int = 0  # 已耗时秒数
        self.gen_error: str = ""  # 生成错误信息


kg_state = KgState()
kg_content_area = None  # ui.refreshable placeholder


def _load_kg_notes():
    """加载有面试题的笔记列表（知识图谱页用）"""
    all_notes = get_notes_cached()
    kg_state.notes_list = []
    for n in all_notes:
        if n.status != "done":
            continue
        try:
            if n.questions:
                kg_state.notes_list.append(n)
        except Exception:
            continue


def _generate_kg_for_note(note_id: int):
    """为已有笔记生成知识图谱（后台线程）"""
    import time
    note = get_note_by_id(note_id)
    if not note or kg_state.generating:
        return
    kg_state.generating = True
    kg_state.gen_start_time = time.time()
    kg_state.gen_elapsed = 0
    kg_state.gen_error = ""

    def _do_generate():
        try:
            from llm_client import LLMClient, SYSTEM_KNOWLEDGE_GRAPH
            llm = LLMClient()
            questions_obj = get_questions_by_note_id(note_id)
            input_text = note.raw_notes[:8000] if note.raw_notes else (questions_obj.content[:8000] if questions_obj else "")
            if not input_text:
                raise ValueError("笔记内容为空")
            result = llm.chat(
                system=SYSTEM_KNOWLEDGE_GRAPH,
                user=input_text,
                temperature=0.1,
                max_tokens=2000,
            )
            save_knowledge_graph(note_id, result)
            return True
        except Exception as e:
            logger.error(f"知识图谱生成失败: {e}")
            return str(e)

    def _run():
        result = _do_generate()
        kg_state.generating = False
        kg_state.gen_elapsed = int(time.time() - kg_state.gen_start_time)
        if result is not True:
            kg_state.gen_error = str(result)

    import threading
    threading.Thread(target=_run, daemon=True).start()


def _on_kg_note_select(note_id: int):
    """选择笔记后加载知识图谱"""
    if not note_id:
        return
    kg_state.current_note_id = note_id
    kg_state.graph_data = None
    kg_state.weak_areas = []
    kg_state.knowledge_points = []
    kg_state.relationships = []
    kg_state.questions = []

    # 加载面试题
    questions_obj = get_questions_by_note_id(note_id)
    if questions_obj:
        kg_state.questions = parse_questions(questions_obj.content)

    raw = get_knowledge_graph(note_id)
    if raw:
        try:
            # 尝试从内容中提取 JSON
            json_str = raw.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("\n", 1)[1]
                if json_str.endswith("```"):
                    json_str = json_str[:json_str.rfind("```")]
            data = json.loads(json_str)
            kg_state.graph_data = data
            kg_state.knowledge_points = data.get("knowledge_points", [])
            kg_state.relationships = data.get("relationships", [])
            kg_state.weak_areas = data.get("weak_areas", [])
        except (json.JSONDecodeError, KeyError):
            pass

    if kg_content_area:
        kg_content_area.refresh()


def _build_echart_option() -> dict:
    """构建 ECharts 力导向图配置"""
    nodes = kg_state.knowledge_points
    edges = kg_state.relationships
    if not nodes:
        return {}

    imp_map = {"高": 50, "中": 35, "低": 22}
    diff_colors = {"基础": "#2563eb", "进阶": "#d97706", "高级": "#e11d48"}
    categories_list = ["基础", "进阶", "高级"]
    categories = [{"name": c, "itemStyle": {"color": diff_colors[c]}} for c in categories_list]

    echart_nodes = []
    for n in nodes:
        diff = n.get("difficulty", "")
        cat_idx = categories_list.index(diff) if diff in categories_list else 0
        symbol_size = imp_map.get(n.get("importance", ""), 30)
        echart_nodes.append({
            "name": n.get("name", ""),
            "id": n.get("id", n.get("name", "")),
            "symbolSize": symbol_size,
            "category": cat_idx,
            "itemStyle": {"color": diff_colors.get(diff, "#2563eb")},
            "label": {"show": True, "fontSize": 12},
        })

    # 关系去重
    seen_edges = set()
    echart_links = []
    for r in edges:
        key = (r.get("source", ""), r.get("target", ""))
        if key not in seen_edges and key[0] and key[1]:
            seen_edges.add(key)
            echart_links.append({
                "source": key[0],
                "target": key[1],
                "label": {"show": True, "formatter": r.get("relation", ""), "fontSize": 10},
                "lineStyle": {"curveness": 0.1},
            })

    return {
        "tooltip": {"trigger": "item"},
        "legend": [{"data": [c["name"] for c in categories], "bottom": 10}],
        "series": [{
            "type": "graph",
            "layout": "force",
            "data": echart_nodes,
            "links": echart_links,
            "categories": categories,
            "roam": True,
            "draggable": True,
            "label": {"position": "right"},
            "force": {
                "repulsion": 300,
                "edgeLength": [80, 200],
                "gravity": 0.1,
            },
            "lineStyle": {"color": "#94a3b8", "opacity": 0.6},
            "emphasis": {
                "focus": "adjacency",
                "lineStyle": {"width": 3},
            },
        }],
    }


def build_knowledge_graph_page():
    """构建知识图谱页面"""
    ui.add_head_html(f"<style>{KG_PAGE_CSS}</style>")
    ui.space().classes("h-6")

    _load_kg_notes()

    # ── 顶部：选择笔记 ──
    with ui.card().classes("card-modern w-full max-w-6xl mx-auto p-6 fade-in"):
        with ui.row().classes("w-full items-center gap-3 mb-4"):
            ui.icon("hub", size="28px").classes("text-primary")
            ui.label("知识图谱").classes("text-xl font-bold")
            ui.badge("知识点关联可视化", color="primary").props("outline").classes("text-xs")

        kg_note_options = {}
        for n in kg_state.notes_list:
            label = f"{n.date} | {n.job_position}"
            kg_note_options[label] = n.id

        if kg_note_options:
            first_label = list(kg_note_options.keys())[0]
            ui.select(
                options=list(kg_note_options.keys()),
                value=first_label,
                label="选择一套面试题",
                on_change=lambda e: _on_kg_note_select(kg_note_options.get(e.value)),
            ).classes("w-full max-w-md").props("outlined dense")
            if not kg_state.current_note_id:
                _on_kg_note_select(kg_note_options[first_label])
        else:
            ui.label("还没有已生成的面试题，请先到首页生成").classes("text-secondary")
            return

    # ── 内容区域（可刷新） ──
    @ui.refreshable
    def kg_content():
        if not kg_state.knowledge_points:
            with ui.card().classes("card-modern w-full max-w-6xl mx-auto p-8 mt-4 text-center"):
                if kg_state.generating:
                    import time
                    elapsed = int(time.time() - kg_state.gen_start_time) if kg_state.gen_start_time else 0
                    ui.spinner(size="48px").classes("text-primary mb-3")
                    ui.label("正在生成知识图谱...").classes("text-lg font-medium text-primary")
                    ui.label(f"LLM 正在分析知识点关联（已等待 {elapsed} 秒）").classes("text-sm text-muted mt-1")
                    ui.label("模型响应时间取决于 API 速度，请耐心等待").classes("text-xs text-muted")
                elif kg_state.gen_error:
                    ui.icon("error_outline", size="48px").classes("text-red-400 mb-2")
                    ui.label("生成失败").classes("text-lg font-medium text-red-500")
                    ui.label(kg_state.gen_error).classes("text-sm text-muted mt-1 max-w-md mx-auto")
                    ui.button(
                        "重试",
                        icon="refresh",
                        on_click=lambda: _generate_kg_for_note(kg_state.current_note_id),
                    ).classes("btn-secondary mt-4")
                else:
                    ui.icon("scatter_plot", size="48px").classes("text-muted opacity-40 mb-2")
                    ui.label("该笔记暂无知识图谱数据").classes("text-lg text-secondary")
                    ui.label("新生成的面试题会自动包含知识图谱，已有笔记可点击下方按钮生成").classes("text-sm text-muted mt-1")
                    ui.button(
                        "生成知识图谱",
                        icon="auto_awesome",
                        on_click=lambda: _generate_kg_for_note(kg_state.current_note_id),
                    ).classes("btn-primary mt-4")
            return

        # ── 统计概览 ──
        with ui.row().classes("w-full max-w-6xl mx-auto gap-4 mt-4"):
            stats = [
                ("知识点", str(len(kg_state.knowledge_points)), "scatter_plot", "text-primary"),
                ("关系数", str(len(kg_state.relationships)), "share", "text-green-600"),
                ("薄弱项", str(len(kg_state.weak_areas)), "warning_amber", "text-orange-500"),
            ]
            for label, value, icon, color in stats:
                with ui.card().classes("card-modern p-4 flex-1 text-center"):
                    ui.icon(icon, size="24px").classes(f"{color} mb-1")
                    ui.label(value).classes(f"text-2xl font-bold {color}")
                    ui.label(label).classes("text-xs text-muted")

        # ── 主体：图谱 + 详情 ──
        with ui.row().classes("w-full max-w-6xl mx-auto gap-4 mt-4"):
            # 左侧：ECharts 力导向图
            with ui.card().classes("card-modern p-4 flex-1"):
                option = _build_echart_option()
                ui.echart(option).classes("w-full").style("height: 450px")

                # 图例说明
                with ui.row().classes("gap-4 mt-3 justify-center text-xs text-muted"):
                    with ui.row().classes("gap-1 items-center"):
                        ui.icon("circle", size="10px").classes("text-primary")
                        ui.label("基础")
                    with ui.row().classes("gap-1 items-center"):
                        ui.icon("circle", size="10px").classes("text-orange-500")
                        ui.label("进阶")
                    with ui.row().classes("gap-1 items-center"):
                        ui.icon("circle", size="10px").classes("text-red-500")
                        ui.label("高级")
                    ui.label("|").classes("text-muted")
                    ui.label("节点越大 = 重要度越高").classes("text-muted")

            # 右侧：知识点 / 薄弱环节 / 面试题
            with ui.card().classes("card-modern p-4 w-[420px] shrink-0"):
                with ui.tabs().classes("w-full mb-3") as kg_tabs:
                    ui.tab("知识点", icon="label")
                    ui.tab("薄弱环节", icon="warning_amber")
                    ui.tab("面试题", icon="quiz")

                with ui.tab_panels(kg_tabs, value="知识点").classes("w-full"):
                    # 知识点列表
                    with ui.tab_panel("知识点"):
                        sorted_kps = sorted(kg_state.knowledge_points, key=lambda x: {"高": 0, "中": 1, "低": 2}.get(x.get("importance", ""), 3))
                        with ui.scroll_area().style("height: 380px"):
                            for i, kp in enumerate(sorted_kps):
                                imp = kp.get("importance", "")
                                imp_color = {"高": "text-red-500", "中": "text-orange-500", "低": "text-green-600"}.get(imp, "text-muted")
                                diff = kp.get("difficulty", "")
                                bg = "bg-primary/5 rounded-lg" if i % 2 == 0 else ""
                                with ui.row().classes(f"w-full items-center gap-3 py-2 px-2 {bg}"):
                                    ui.icon("label", size="14px").classes("text-primary opacity-60 shrink-0")
                                    with ui.column().classes("flex-1 gap-0"):
                                        ui.label(kp.get("name", "")).classes("text-sm font-medium")
                                        with ui.row().classes("gap-2 mt-0.5"):
                                            if diff:
                                                ui.label(diff).classes("text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary")
                                            if imp:
                                                ui.label(f"重要度:{imp}").classes(f"text-xs {imp_color}")

                    # 薄弱环节
                    with ui.tab_panel("薄弱环节"):
                        if kg_state.weak_areas:
                            with ui.scroll_area().style("height: 380px"):
                                with ui.column().classes("gap-3"):
                                    for wa in kg_state.weak_areas:
                                        with ui.card().classes("kg-weak-card"):
                                            with ui.row().classes("items-center gap-2 mb-1"):
                                                ui.icon("warning_amber", size="16px").classes("text-orange-500")
                                                ui.label(wa.get("topic", "")).classes("text-sm font-semibold")
                                            if wa.get("reason"):
                                                ui.label(f"原因：{wa['reason']}").classes("text-xs text-secondary mt-1")
                                            if wa.get("suggestion"):
                                                ui.label(f"建议：{wa['suggestion']}").classes("text-xs text-primary mt-1")
                        else:
                            with ui.column().classes("items-center py-8 text-muted"):
                                ui.icon("check_circle", size="32px").classes("opacity-40 mb-2")
                                ui.label("暂无薄弱环节").classes("text-sm")

                    # 面试题
                    with ui.tab_panel("面试题"):
                        if kg_state.questions:
                            with ui.scroll_area().style("height: 380px"):
                                with ui.column().classes("gap-1"):
                                    for q in kg_state.questions:
                                        with ui.expansion(
                                            f"Q{q['num']}. {q['title'][:30]}{'...' if len(q['title']) > 30 else ''}",
                                            icon="help_outline",
                                        ).classes("w-full").props("dense expand-icon-toggle flat"):
                                            with ui.column().classes("gap-2 p-2"):
                                                if q["difficulty"] or q["category"]:
                                                    with ui.row().classes("gap-2"):
                                                        if q["difficulty"]:
                                                            ui.badge(q["difficulty"], color="primary").props("outline").classes("text-xs")
                                                        if q["category"]:
                                                            ui.badge(q["category"], color="secondary").props("outline").classes("text-xs")
                                                if q["knowledge"]:
                                                    with ui.row().classes("gap-1 flex-wrap"):
                                                        for tag in q["knowledge"].split("、"):
                                                            ui.label(tag.strip()).classes("text-xs px-1.5 py-0.5 rounded bg-primary/5 text-primary")
                                                if q["answer"]:
                                                    ui.markdown(q["answer"]).classes("markdown-content text-sm")
                                                else:
                                                    ui.markdown(q["full_text"]).classes("markdown-content text-sm")
                        else:
                            with ui.column().classes("items-center py-8 text-muted"):
                                ui.icon("quiz", size="32px").classes("opacity-40 mb-2")
                                ui.label("暂无面试题").classes("text-sm")

    global kg_content_area
    kg_content_area = kg_content
    kg_content()

    # 轮询：生成中每秒刷新计时，完成后加载图谱数据并刷新
    was_generating = [kg_state.generating]

    def _check_gen_done():
        if was_generating[0] and not kg_state.generating:
            was_generating[0] = False
            _on_kg_note_select(kg_state.current_note_id)  # 从数据库加载刚生成的图谱
            return
        elif kg_state.generating:
            kg_content_area.refresh()  # 每秒刷新计时
        was_generating[0] = kg_state.generating

    ui.timer(1.0, _check_gen_done, once=False)


# ══════════════════════════════════════════════════
# 题库自测
# ══════════════════════════════════════════════════

class QuizState:
    """题库自测状态"""
    def __init__(self):
        self.note_id: Optional[int] = None
        self.questions: list[dict] = []  # 所有题目
        self.filtered: list[dict] = []   # 当前筛选后的题目
        self.records: dict[int, bool] = {}  # {index: mastered}
        self.current_idx: int = 0
        self.show_answer: bool = False
        self.notes_list: list = []
        self.filter_mode: str = "all"  # all / untested / unmastered
        self.shuffled: bool = False


quiz_state = QuizState()
quiz_content_area = None  # ui.refreshable placeholder


def _load_quiz_notes():
    """加载有面试题的笔记列表"""
    all_notes = get_notes_cached()
    quiz_state.notes_list = []
    for n in all_notes:
        if n.status != "done":
            continue
        try:
            if n.questions:
                quiz_state.notes_list.append(n)
        except Exception:
            continue


def _on_quiz_note_select(note_id: int):
    """选择笔记后加载题目"""
    if not note_id:
        return
    questions_obj = get_questions_by_note_id(note_id)
    if not questions_obj:
        return

    quiz_state.note_id = note_id
    quiz_state.questions = parse_questions(questions_obj.content)
    quiz_state.filtered = list(quiz_state.questions)
    quiz_state.records = get_quiz_records(note_id)
    quiz_state.current_idx = 0
    quiz_state.show_answer = False
    quiz_state.filter_mode = "all"
    quiz_state.shuffled = False
    if quiz_content_area:
        quiz_content_area.refresh()


def _apply_filter():
    """根据筛选模式过滤题目"""
    qs = list(quiz_state.questions)
    if quiz_state.filter_mode == "untested":
        qs = [q for q in qs if q["index"] not in quiz_state.records]
    elif quiz_state.filter_mode == "unmastered":
        qs = [q for q in qs if quiz_state.records.get(q["index"]) is False]
    if quiz_state.shuffled:
        import random
        random.shuffle(qs)
    quiz_state.filtered = qs
    quiz_state.current_idx = 0
    quiz_state.show_answer = False
    if quiz_content_area:
        quiz_content_area.refresh()


def _toggle_shuffle():
    """切换打乱顺序"""
    quiz_state.shuffled = not quiz_state.shuffled
    _apply_filter()


def _set_filter_mode(mode: str):
    """设置筛选模式"""
    quiz_state.filter_mode = mode
    _apply_filter()


def _retry_wrong():
    """错题重练：只显示未掌握的题目"""
    quiz_state.filter_mode = "unmastered"
    quiz_state.shuffled = True
    _apply_filter()


def _mark_mastery(mastered: bool):
    """标记掌握/未掌握，自动跳下一题"""
    if not quiz_state.filtered or quiz_state.current_idx >= len(quiz_state.filtered):
        return
    q = quiz_state.filtered[quiz_state.current_idx]
    save_quiz_record(quiz_state.note_id, q["index"], mastered)
    quiz_state.records[q["index"]] = mastered
    quiz_state.show_answer = False
    # 如果是未掌握筛选模式，标记已掌握后从列表移除
    if quiz_state.filter_mode == "unmastered" and mastered:
        quiz_state.filtered.pop(quiz_state.current_idx)
        if quiz_state.current_idx >= len(quiz_state.filtered):
            quiz_state.current_idx = max(0, len(quiz_state.filtered) - 1)
    elif quiz_state.current_idx < len(quiz_state.filtered) - 1:
        quiz_state.current_idx += 1
    if quiz_content_area:
        quiz_content_area.refresh()


def _quiz_goto(idx: int):
    """跳转到指定题目"""
    if 0 <= idx < len(quiz_state.filtered):
        quiz_state.current_idx = idx
        quiz_state.show_answer = False
        if quiz_content_area:
            quiz_content_area.refresh()


def _quiz_next():
    """下一题"""
    if quiz_state.current_idx < len(quiz_state.filtered) - 1:
        quiz_state.current_idx += 1
        quiz_state.show_answer = False
        if quiz_content_area:
            quiz_content_area.refresh()


def _quiz_prev():
    """上一题"""
    if quiz_state.current_idx > 0:
        quiz_state.current_idx -= 1
        quiz_state.show_answer = False
        if quiz_content_area:
            quiz_content_area.refresh()


def _reset_quiz():
    """重置当前笔记的自测记录"""
    if quiz_state.note_id:
        reset_quiz_records(quiz_state.note_id)
        quiz_state.records = {}
        quiz_state.current_idx = 0
        quiz_state.show_answer = False
        quiz_state.filtered = list(quiz_state.questions)
        quiz_state.filter_mode = "all"
        quiz_state.shuffled = False
        if quiz_content_area:
            quiz_content_area.refresh()


async def _handle_upload(e):
    """处理上传的 markdown 文件"""
    content = await e.file.text("utf-8")
    filename = e.file.name
    success, msg, count = import_questions_from_markdown(content, filename)
    if success:
        ui.notify(f"✅ {msg}", type="positive", position="top")
        invalidate_notes_cache()
        # 刷新整个页面以更新下拉列表
        ui.navigate.to("/")
    else:
        ui.notify(f"⚠️ {msg}", type="warning", position="top")


def auto_scan_import():
    """启动时自动扫描项目目录下的面试题*.md 文件"""
    import logging
    logger = logging.getLogger(__name__)
    md_files = list(Path(__file__).parent.glob("面试题*.md"))
    if not md_files:
        return
    imported = 0
    for fp in md_files:
        content = fp.read_text(encoding="utf-8")
        success, msg, _ = import_questions_from_markdown(content, fp.name)
        if success:
            imported += 1
            logger.info("自动导入: %s", msg)
    if imported:
        logger.info("自动扫描完成，共导入 %d 个面试题文件", imported)


def build_quiz_page():
    """构建题库自测页面"""
    global quiz_content_area
    ui.space().classes("h-6")

    _load_quiz_notes()

    # ── 顶部：选择笔记 ──
    with ui.card().classes("card-modern w-full max-w-6xl mx-auto p-6 fade-in"):
        with ui.row().classes("w-full items-center justify-between mb-4"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("quiz", size="28px").classes("text-primary")
                ui.label("面试题库").classes("text-xl font-bold")
                ui.badge("自测 · 掌握检测", color="primary").props("outline").classes("text-xs")
            ui.upload(on_upload=_handle_upload, auto_upload=True).props(
                'accept=.md flat bordered dense'
            ).classes("btn-secondary").tooltip("导入 .md 面试题文件")

        note_options = {}
        for n in quiz_state.notes_list:
            label = f"{n.date} | {n.job_position} | {len(n.questions)}题"
            note_options[label] = n.id

        if note_options:
            first_label = list(note_options.keys())[0]
            ui.select(
                options=list(note_options.keys()),
                value=first_label,
                label="选择一套面试题",
                on_change=lambda e: _on_quiz_note_select(note_options.get(e.value)),
            ).classes("w-full max-w-md").props("outlined dense")
            if not quiz_state.questions:
                _on_quiz_note_select(note_options[first_label])
        else:
            ui.label("还没有已生成的面试题，请先到首页生成").classes("text-secondary")
            return

    # ── 题目内容区域（可刷新） ──
    @ui.refreshable
    def quiz_content():
        if not quiz_state.filtered and quiz_state.questions:
            quiz_state.filtered = list(quiz_state.questions)

        if not quiz_state.filtered:
            # 当前筛选无结果
            with ui.card().classes("card-modern w-full max-w-6xl mx-auto p-8 mt-4 text-center"):
                mode_label = {"untested": "未测试", "unmastered": "未掌握"}.get(quiz_state.filter_mode, "")
                ui.icon("filter_alt_off", size="48px").classes("text-muted opacity-40 mb-2")
                ui.label(f"当前没有{mode_label}的题目").classes("text-lg text-secondary")
                with ui.row().classes("gap-3 mt-4 justify-center"):
                    ui.button("显示全部", on_click=lambda: _set_filter_mode("all")).classes("btn-secondary")
                    ui.button("🔄 重置记录", on_click=lambda: (_reset_quiz(), ui.notify("已重置"))).classes("btn-ghost")
            return

        qs = quiz_state.filtered
        cur = min(quiz_state.current_idx, len(qs) - 1)
        quiz_state.current_idx = cur
        q = qs[cur]
        total_all = len(quiz_state.questions)
        total_filtered = len(qs)
        tested = len(quiz_state.records)
        mastered_count = sum(1 for v in quiz_state.records.values() if v)
        unmastered_count = tested - mastered_count
        progress_pct = tested / total_all if total_all else 0

        # ── 全局进度条 ──
        with ui.row().classes("w-full max-w-6xl mx-auto gap-4 mt-4 items-center"):
            ui.linear_progress(value=progress_pct, show_value=False).classes(
                "flex-1 h-2 rounded-full"
            ).props("color=primary track-color=grey-3")
            ui.label(f"{tested}/{total_all}").classes("text-sm text-secondary font-mono shrink-0")

        # ── 筛选工具栏 ──
        with ui.row().classes("w-full max-w-6xl mx-auto gap-2 mt-3 items-center flex-wrap"):
            filter_btns = [
                ("all", "全部", f"{total_all}"),
                ("untested", "未测试", f"{total_all - tested}"),
                ("unmastered", "未掌握", f"{unmastered_count}"),
            ]
            for mode, label, count in filter_btns:
                is_active = quiz_state.filter_mode == mode
                btn_cls = "btn-primary text-xs" if is_active else "btn-secondary text-xs"
                ui.button(
                    f"{label} ({count})",
                    on_click=lambda m=mode: _set_filter_mode(m),
                ).classes(btn_cls).props("dense")

            # 打乱按钮
            shuffle_cls = "btn-primary text-xs" if quiz_state.shuffled else "btn-secondary text-xs"
            ui.button(
                icon="shuffle",
                on_click=_toggle_shuffle,
            ).classes(shuffle_cls).props("dense").tooltip("打乱顺序")

            # 错题重练
            if unmastered_count > 0:
                ui.button(
                    "错题重练",
                    icon="replay",
                    on_click=_retry_wrong,
                ).classes("btn-secondary text-xs !text-red-500").props("dense outline")

            ui.space()
            ui.label(f"当前 {total_filtered} 题").classes("text-xs text-muted")

        # ── 左右分栏 ──
        with ui.row().classes("w-full max-w-6xl mx-auto gap-4 mt-3"):
            # 左侧：题目列表
            with ui.card().classes("card-modern p-4 w-72 shrink-0"):
                ui.label("题目列表").classes("text-base font-bold mb-3")
                with ui.scroll_area().classes("h-80"):
                    for i, item in enumerate(qs):
                        mastered = quiz_state.records.get(item["index"])
                        if mastered is True:
                            icon_name, color = "check_circle", "text-green-500"
                        elif mastered is False:
                            icon_name, color = "cancel", "text-red-400"
                        else:
                            icon_name, color = "radio_button_unchecked", "text-grey"

                        bg = "bg-primary/10 rounded-lg " if i == cur else ""

                        with ui.row().classes(f"w-full items-center gap-2 py-1.5 px-2 cursor-pointer {bg}").on(
                            "click", lambda idx=i: _quiz_goto(idx)
                        ):
                            ui.icon(icon_name, size="18px").classes(color)
                            ui.label(f"Q{item['num']}").classes("text-sm font-semibold shrink-0")
                            title_text = item["title"][:18] + ("..." if len(item["title"]) > 18 else "")
                            ui.label(title_text).classes("text-xs text-secondary truncate")

                # 左侧统计
                ui.html("<hr class='divider-gradient' />")
                rate = f"{mastered_count/tested*100:.0f}%" if tested > 0 else "--"
                with ui.column().classes("w-full gap-1 mt-2"):
                    with ui.row().classes("w-full justify-between text-sm"):
                        ui.label("已测").classes("text-secondary")
                        ui.label(f"{tested}/{total_all}").classes("font-semibold")
                    with ui.row().classes("w-full justify-between text-sm"):
                        ui.label("已掌握").classes("text-secondary")
                        ui.label(f"{mastered_count}").classes("font-semibold text-green-600")
                    with ui.row().classes("w-full justify-between text-sm"):
                        ui.label("未掌握").classes("text-secondary")
                        ui.label(f"{unmastered_count}").classes("font-semibold text-red-500")
                    with ui.row().classes("w-full justify-between text-sm"):
                        ui.label("掌握率").classes("text-secondary")
                        ui.label(f"{rate}").classes("font-bold text-primary")

            # 右侧：自测区域
            with ui.card().classes("card-modern p-6 flex-1"):
                # 题目进度指示
                with ui.row().classes("w-full items-center justify-between mb-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.badge(f"Q{q['num']}", color="primary").classes("text-sm")
                        if q["difficulty"]:
                            diff_color = {"高": "red", "中": "orange", "低": "green"}.get(q["difficulty"][0] if q["difficulty"] else "", "primary")
                            ui.label(q["difficulty"]).classes(
                                f"text-xs px-2 py-0.5 rounded-full bg-{diff_color}/10 text-{diff_color}"
                            )
                        if q["category"]:
                            ui.label(q["category"]).classes("text-xs px-2 py-0.5 rounded-full bg-surface-alt border border-border")
                        # 当前题的掌握状态
                        m = quiz_state.records.get(q["index"])
                        if m is True:
                            ui.icon("check_circle", size="18px").classes("text-green-500")
                        elif m is False:
                            ui.icon("cancel", size="18px").classes("text-red-400")
                    ui.label(f"{cur + 1} / {total_filtered}").classes("text-sm text-secondary font-mono")

                # 微型进度条
                if total_filtered > 1:
                    ui.linear_progress(
                        value=(cur + 1) / total_filtered, show_value=False
                    ).classes("w-full h-1 rounded-full mb-3").props("color=primary track-color=grey-3")

                # 知识点标签
                if q["knowledge"]:
                    with ui.row().classes("w-full gap-2 mb-3 flex-wrap"):
                        for tag in q["knowledge"].split("、"):
                            ui.badge(tag.strip(), color="secondary").props("outline").classes("text-xs")

                # 题目内容
                ui.html("<hr class='divider-gradient' />")
                ui.markdown(f"### Q{q['num']}. {q['title']}").classes("mt-3")

                # 答案区域
                with ui.expansion("💡 查看答案", icon="lightbulb").classes("w-full mt-4").props(
                    "header-class='text-primary font-semibold'"
                ):
                    if q["answer"]:
                        ui.markdown(q["answer"]).classes("markdown-content")
                    else:
                        ui.markdown(q["full_text"]).classes("markdown-content")

                # 操作按钮
                ui.html("<hr class='divider-gradient mt-4' />")
                with ui.row().classes("w-full justify-center gap-4 mt-4"):
                    ui.button("❌ 未掌握", color="red").on(
                        "click", lambda: (_mark_mastery(False), ui.notify("已标记为未掌握", type="warning"))
                    ).classes("px-6").props("outline")
                    ui.button("✅ 已掌握", color="green").on(
                        "click", lambda: (_mark_mastery(True), ui.notify("已标记为已掌握", type="positive"))
                    ).classes("px-6")

                # 底部导航 + 快捷键提示
                with ui.row().classes("w-full justify-between mt-4 items-center"):
                    ui.button("⬅ 上一题", icon="arrow_back").on(
                        "click", _quiz_prev
                    ).props("flat").bind_enabled_from(quiz_state, "current_idx", lambda v: v > 0)

                    ui.label("← → 导航 | 1 未掌握 2 已掌握").classes("text-xs text-muted")

                    with ui.row().classes("gap-2"):
                        ui.button("🔄 重置", on_click=lambda: (_reset_quiz(), ui.notify("已重置"))).props("flat").classes("btn-ghost")
                        ui.button("下一题 ➡", icon="arrow_forward").on(
                            "click", _quiz_next
                        ).props("flat")

                # 键盘快捷键
                ui.keyboard(on_key=lambda e: _on_quiz_key(e))

        # ── 完成总结 ──
        all_tested = all(q["index"] in quiz_state.records for q in qs)
        if all_tested and total_filtered > 0:
            m_count = sum(1 for q in qs if quiz_state.records.get(q["index"]) is True)
            u_count = total_filtered - m_count
            rate_val = m_count / total_filtered * 100
            with ui.card().classes("card-modern w-full max-w-6xl mx-auto p-6 mt-4 text-center fade-in"):
                if rate_val == 100:
                    ui.icon("emoji_events", size="48px").classes("text-yellow-500 mb-2")
                    ui.label("恭喜全部掌握！").classes("text-xl font-bold text-green-600")
                elif rate_val >= 80:
                    ui.icon("thumb_up", size="48px").classes("text-primary mb-2")
                    ui.label("掌握情况良好！").classes("text-xl font-bold text-primary")
                else:
                    ui.icon("school", size="48px").classes("text-orange-500 mb-2")
                    ui.label("还需要加油！").classes("text-xl font-bold text-orange-600")

                with ui.row().classes("gap-8 mt-3 justify-center"):
                    with ui.column().classes("items-center"):
                        ui.label(f"{total_filtered}").classes("text-2xl font-bold")
                        ui.label("总题数").classes("text-xs text-muted")
                    with ui.column().classes("items-center"):
                        ui.label(f"{m_count}").classes("text-2xl font-bold text-green-600")
                        ui.label("已掌握").classes("text-xs text-muted")
                    with ui.column().classes("items-center"):
                        ui.label(f"{u_count}").classes("text-2xl font-bold text-red-500")
                        ui.label("未掌握").classes("text-xs text-muted")
                    with ui.column().classes("items-center"):
                        ui.label(f"{rate_val:.0f}%").classes("text-2xl font-bold text-primary")
                        ui.label("掌握率").classes("text-xs text-muted")

                with ui.row().classes("gap-3 mt-4 justify-center"):
                    if u_count > 0:
                        ui.button("错题重练", icon="replay", on_click=_retry_wrong).classes("btn-primary")
                    ui.button("重置再来", icon="refresh", on_click=lambda: (_reset_quiz(), ui.notify("已重置"))).classes("btn-secondary")

    quiz_content_area = quiz_content
    quiz_content()


def _on_quiz_key(e):
    """题库页面键盘快捷键"""
    if e.key.arrow_left:
        _quiz_prev()
    elif e.key.arrow_right:
        _quiz_next()
    elif e.key.number == 1:
        _mark_mastery(False)
        ui.notify("已标记为未掌握", type="warning")
    elif e.key.number == 2:
        _mark_mastery(True)
        ui.notify("已标记为已掌握", type="positive")


# 表单状态
# ══════════════════════════════════════════════════

class FormState:
    """统一管理表单状态"""
    def __init__(self):
        self.date = date_today.today().isoformat()
        self.job_position = JOB_POSITIONS[0]
        self.notes = ""
        self.generating = False
        self.progress_value = 0.0
        self.progress_msg = ""
        self.show_result = False
        self.result_content = ""
        self.question_count = 0
        self.debug_url = ""
        self.show_debug = False
        self.debug_url_label = ""
        self.show_custom_job = False
        # 流式生成相关
        self.streaming_content = ""  # 流式累积内容
        self.current_step = 0  # 当前步骤 0-6
        self.step_label = ""  # 当前步骤名称
        self.question_count_label = ""  # 题目数量标签


form_state = FormState()


# ══════════════════════════════════════════════════
# 事件处理
# ══════════════════════════════════════════════════

def _on_job_change(e):
    """岗位选择变更"""
    form_state.job_position = e.value
    form_state.show_custom_job = e.value == "自定义岗位"


def _clear_form():
    """清空表单"""
    form_state.notes = ""
    form_state.show_result = False
    form_state.generating = False
    form_state.streaming_content = ""
    form_state.current_step = 0


def _start_generate():
    """开始生成面试题"""
    notes = form_state.notes.strip()
    if not notes:
        ui.notify("请先输入学习笔记！", type="warning", position="top")
        return
    if len(notes) < 20:
        ui.notify("笔记内容过短，请至少输入 20 个字符", type="warning", position="top")
        return

    # 重置状态
    form_state.generating = True
    form_state.progress_value = 0.0
    form_state.progress_msg = "准备中..."
    form_state.show_result = False
    form_state.result_content = ""
    form_state.streaming_content = ""
    form_state.current_step = 0
    form_state.step_label = "准备中..."

    ui.notify("🚀 任务已提交，正在生成面试题...", type="ongoing", position="top")

    # 启动后台任务
    global CURRENT_TASK_ID, CURRENT_TIMER
    CURRENT_TASK_ID = start_generate_task(
        date=form_state.date,
        raw_notes=notes,
        job_position=form_state.job_position,
        on_update=_on_task_update,
    )
    invalidate_notes_cache()

    # 取消旧的轮询定时器，再启动新的
    if CURRENT_TIMER:
        try:
            CURRENT_TIMER.deactivate()
        except Exception:
            pass
    CURRENT_TIMER = ui.timer(0.3, _poll_task, once=False)


def _on_task_update(task_dict: dict):
    """后台线程回调更新"""
    pass


def _poll_task():
    """轮询任务状态（每 0.3 秒）"""
    global CURRENT_TASK_ID, CURRENT_TIMER
    if not CURRENT_TASK_ID:
        return

    task = get_task(CURRENT_TASK_ID)
    if not task:
        return

    # 实时同步流式内容
    form_state.streaming_content = task.streaming_content
    form_state.current_step = task.current_step
    form_state.step_label = task.progress_msg

    if task.status.value == "done":
        # 生成完成 — 保留流式卡片内容，显示操作按钮
        form_state.generating = False
        form_state.show_result = True
        form_state.result_content = task.result
        form_state.streaming_content = task.result
        form_state.question_count = task.question_count
        form_state.question_count_label = f"共 {task.question_count} 道面试题"

        ui.notify(
            f"✅ 生成完成！共 {task.question_count} 道面试题",
            type="positive",
            position="top",
        )
        _stop_timer()
        return False

    elif task.status.value == "failed":
        # 失败 — 保留已生成的内容，显示错误提示
        form_state.generating = False
        form_state.show_result = True
        form_state.result_content = task.streaming_content  # 保留部分结果
        form_state.step_label = f"❌ 生成失败: {task.error}"

        ui.notify(f"❌ 生成失败: {task.error}", type="negative", position="top", multi_line=True)
        _stop_timer()
        return False

    return True  # 继续轮询


def _stop_timer():
    """停止当前轮询定时器"""
    global CURRENT_TIMER
    if CURRENT_TIMER:
        try:
            CURRENT_TIMER.deactivate()
        except Exception:
            pass
        CURRENT_TIMER = None


def _copy_result():
    """复制结果到剪贴板"""
    if form_state.result_content:
        ui.clipboard.write(form_state.result_content)
        ui.notify("✅ 已复制到剪贴板！", type="positive", position="top")


def _export_markdown():
    """导出为 Markdown 文件"""
    if not form_state.result_content:
        return

    content = form_state.result_content
    filename = f"面试题_{form_state.date}_{form_state.job_position}.md"
    # 清理文件名中的非法字符
    filename = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        ui.notify(f"✅ 已导出为 {filename}", type="positive", position="top")
    except Exception as e:
        ui.notify(f"❌ 导出失败: {e}", type="negative", position="top")


def _regenerate():
    """重新生成"""
    form_state.show_result = False
    _start_generate()


def _refresh_history():
    """刷新历史记录（手动刷新 → 绕过缓存）"""
    invalidate_notes_cache()
    ui.navigate.reload()


def _view_history(note):
    """查看历史记录详情"""
    questions = get_questions_by_note_id(note.id)
    if not questions:
        ui.notify("该记录暂无面试题数据", type="warning", position="top")
        return

    with ui.dialog().classes("dialog-modern w-full max-w-4xl") as dialog, ui.card().classes("w-full p-6"):
        with ui.row().classes("w-full justify-between items-center mb-4"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("description", size="24px").classes("text-primary")
                ui.label(f"{note.date} | {note.job_position}").classes("text-xl font-bold")
            ui.button("关闭", icon="close").props("flat").classes("btn-ghost").on("click", dialog.close)
        ui.html("<hr class='divider-gradient' />")
        ui.markdown(questions.content).classes("markdown-content")
    dialog.open()


def _confirm_delete(note):
    """确认删除"""
    with ui.dialog().classes("dialog-modern") as dialog, ui.card().classes("p-6"):
        with ui.column().classes("items-center gap-3"):
            ui.icon("warning_amber", size="40px").classes("text-negative")
            ui.label("确认删除").classes("text-lg font-bold")
            ui.label(f"确定要删除 {note.date} 的记录吗？").classes("")
            ui.label("此操作不可撤销。").classes("text-sm text-muted")
        with ui.row().classes("gap-4 mt-4 justify-center"):
            ui.button("取消", on_click=dialog.close).classes("btn-ghost")
            ui.button("确认删除", color="negative", icon="delete").on(
                "click", lambda: (_do_delete(note.id), dialog.close())
            ).classes("btn-primary !bg-red-500 !shadow-red-500/30")
    dialog.open()


def _do_delete(note_id: int):
    """执行删除"""
    try:
        delete_note(note_id)
        ui.notify("🗑️ 已删除", type="positive", position="top")
        _refresh_history()
    except Exception as e:
        ui.notify(f"删除失败: {e}", type="negative", position="top")


# ══════════════════════════════════════════════════
# 应用入口
# ══════════════════════════════════════════════════

@ui.page("/")
def main_page():
    """主页面"""

    # 注入全局 CSS
    inject_global_styles()

    # 初始化 question_count_label
    form_state.question_count_label = ""

    # 导航
    tabs = create_nav_tabs()

    # 页面内容（根据 tab 切换）
    with ui.tab_panels(tabs, value="首页").classes("w-full"):
        with ui.tab_panel("首页"):
            build_home_page()

        with ui.tab_panel("历史记录"):
            build_history_page()

        with ui.tab_panel("题库"):
            build_quiz_page()

        with ui.tab_panel("知识图谱"):
            build_knowledge_graph_page()

    # 底部信息
    with ui.footer().classes("app-footer justify-center"):
        ui.label("📚 每日学习笔记 → 岗位面试题生成器 | Powered by Coze AI | 数据仅保存在本地")


# ── 启动 ──
if __name__ in {"__main__", "__mp_main__"}:
    logger.info("=" * 50)
    logger.info("启动应用: %s", settings.APP_TITLE)
    logger.info("访问地址: http://%s:%s", settings.APP_HOST, settings.APP_PORT)
    logger.info("=" * 50)

    # 自动扫描导入面试题 markdown 文件
    auto_scan_import()

    ui.run(
        title=settings.APP_TITLE,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        dark=settings.APP_DARK_MODE,
        language=settings.APP_LANGUAGE,
        favicon="📚",
        show=False,
    )
