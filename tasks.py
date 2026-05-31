"""异步任务队列 — 后台执行 AI 生成，不阻塞 UI"""
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from config import settings
from models import (
    create_note, get_note_by_id, get_questions_by_note_id,
    save_questions, save_knowledge_graph, update_note_status,
)

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class GenerateTask:
    """单个生成任务的状态"""
    id: str  # note_id 的字符串形式
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    progress_msg: str = "排队中..."
    error: str = ""
    result: str = ""
    question_count: int = 0
    debug_url: str = ""
    execute_id: str = ""
    streaming_content: str = ""  # 流式累积内容 (全部)
    step_contents: dict = field(default_factory=dict)  # {step_idx: "content"} 每步独立内容
    step_status: dict = field(default_factory=dict)  # {step_idx: "pending"|"running"|"done"|"failed"}
    current_step: int = 0  # 当前步骤 (1-6)
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    on_update: Optional[Callable] = None  # 回调通知 UI 更新

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "progress": self.progress,
            "progress_msg": self.progress_msg,
            "error": self.error,
            "result": self.result,
            "question_count": self.question_count,
            "debug_url": self.debug_url,
            "execute_id": self.execute_id,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


# 全局任务存储
_tasks: dict[str, GenerateTask] = {}


def get_task(note_id: str) -> Optional[GenerateTask]:
    return _tasks.get(note_id)


def get_all_tasks() -> list[GenerateTask]:
    return list(_tasks.values())


def start_generate_task(
    date: str,
    raw_notes: str,
    job_position: str,
    on_update: Optional[Callable] = None,
) -> str:
    """启动后台生成任务，返回 task_id (即 note_id)"""
    # 1. 先存笔记到数据库
    note = create_note(date=date, raw_notes=raw_notes, job_position=job_position)
    note_id = str(note.id)

    # 2. 创建任务状态
    task = GenerateTask(
        id=note_id,
        status=TaskStatus.PENDING,
        on_update=on_update,
    )
    _tasks[note_id] = task

    # 3. 后台线程执行
    thread = threading.Thread(
        target=_run_task,
        args=(note_id, date, raw_notes, job_position),
        daemon=True,
    )
    thread.start()

    return note_id


def _run_task(note_id: str, date: str, raw_notes: str, job_position: str):
    """后台线程执行体"""
    task = _tasks.get(note_id)
    if not task:
        return

    try:
        task.status = TaskStatus.RUNNING

        # 阶段 1：预处理
        task.progress = 10
        task.progress_msg = "笔记预处理中..."
        _notify(task)
        _update_db(note_id, "processing")

        # 根据引擎选择执行方式
        if settings.AI_ENGINE == "coze":
            from coze_client import CozeClient

            task.progress = 30
            task.progress_msg = "正在调用 Coze 工作流..."
            _notify(task)

            client = CozeClient()
            params = {
                "date": date,
                "position": job_position,
                "raw_notes": raw_notes,
            }
            result = client.run_workflow(params, timeout=settings.TASK_TIMEOUT)

            task.progress = 70
            task.progress_msg = "解析生成结果..."
            _notify(task)

            output = client.parse_output(result)
            debug_url = client.get_debug_url(result)
            execute_id = client.get_execute_id(result)
        else:
            from llm_client import LLMClient, run_pipeline

            task.progress = 15
            task.progress_msg = "正在调用 LLM 生成面试题..."
            _notify(task)

            llm = LLMClient()
            result = run_pipeline(
                llm, raw_notes, job_position, date,
                progress_callback=lambda pct, msg: (
                    setattr(task, 'progress', int(15 + pct * 0.8)),
                    setattr(task, 'progress_msg', msg),
                ),
                on_stream=lambda content, step_idx, step_content: (
                    setattr(task, 'streaming_content', content),
                    task.step_contents.__setitem__(step_idx, step_content),
                ),
                on_step=lambda idx, label: (
                    setattr(task, 'current_step', idx),
                    setattr(task, 'step_status', dict(task.step_status) | {idx: "running"}),
                    setattr(task, 'progress_msg', f"步骤 {idx}/6: {label}"),
                ),
            )
            output = result["output"]
            debug_url = ""
            execute_id = ""

            # 同步步骤状态
            pipeline_step_status = result.get("step_status", {})
            task.step_status = dict(pipeline_step_status)

            # 保存知识图谱
            kg_data = result.get("knowledge_graph", "")
            if kg_data:
                try:
                    save_knowledge_graph(int(note_id), kg_data)
                except Exception:
                    pass

        # 估算题目数量
        question_count = output.count("**Q") if output else 0

        # 保存到数据库
        save_questions(
            note_id=int(note_id),
            content=output,
            question_count=question_count,
        )
        update_note_status(int(note_id), "done")

        # 完成
        task.status = TaskStatus.DONE
        task.progress = 100
        task.progress_msg = "生成完成！"
        task.result = output
        task.question_count = question_count
        task.debug_url = debug_url
        task.execute_id = execute_id
        task.finished_at = time.time()
        _notify(task)

        logger.info(
            "任务完成: note_id=%s, questions=%d, engine=%s",
            note_id, question_count, settings.AI_ENGINE,
        )

    except Exception as e:
        logger.error("任务失败: note_id=%s, error=%s", note_id, str(e))
        # 保存已生成的部分内容（即使失败也不丢数据）
        partial_content = getattr(task, 'streaming_content', "") or ""
        if partial_content:
            try:
                save_questions(
                    note_id=int(note_id),
                    content=partial_content,
                    question_count=partial_content.count("**Q"),
                )
            except Exception:
                pass
        task.status = TaskStatus.FAILED
        task.progress = 0
        task.progress_msg = "生成失败"
        task.error = str(e)
        task.finished_at = time.time()
        _notify(task)
        update_note_status(int(note_id), "failed", str(e))


def _notify(task: GenerateTask):
    """通知 UI 更新"""
    if task.on_update:
        try:
            task.on_update(task.to_dict())
        except Exception:
            pass


def _update_db(note_id: str, status: str):
    """更新数据库状态"""
    try:
        update_note_status(int(note_id), status)
    except Exception:
        pass
