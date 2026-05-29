"""SQLite 数据模型 — 用于本地持久化"""
import json
import re
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine,
)
from sqlalchemy.orm import Session, declarative_base, relationship, selectinload

from config import settings

Base = declarative_base()


# ── 笔记表 ──
class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    date = Column(String(20), nullable=False, comment="学习日期")
    raw_notes = Column(Text, nullable=False, comment="原始笔记 Markdown")
    cleaned_notes = Column(Text, nullable=True, comment="AI 清洗后笔记")
    job_position = Column(String(100), nullable=False, comment="目标岗位")
    status = Column(String(20), default="pending", comment="pending/done/failed")
    error_msg = Column(Text, nullable=True)

    # 关联的面试题
    questions = relationship("InterviewQuestion", back_populates="note", cascade="all, delete-orphan")
    # 关联的知识图谱
    knowledge_graphs = relationship("KnowledgeGraph", back_populates="note", cascade="all, delete-orphan")


# ── 面试题表 ──
class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    content = Column(Text, nullable=False, comment="面试题完整 Markdown")
    question_count = Column(Integer, default=0, comment="题目数量")
    difficulty_distribution = Column(String(200), nullable=True, comment="难度分布 JSON")

    note = relationship("Note", back_populates="questions")


# ── 知识图谱表 ──
class KnowledgeGraph(Base):
    __tablename__ = "knowledge_graph"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    graph_data = Column(Text, nullable=False, comment="知识图谱 JSON 数据")

    note = relationship("Note", back_populates="knowledge_graphs")


# ── 自测记录表 ──
class QuizRecord(Base):
    __tablename__ = "quiz_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=False)
    question_index = Column(Integer, nullable=False, comment="题目序号 (1-based)")
    mastered = Column(Boolean, nullable=False, comment="True=掌握, False=未掌握")
    tested_at = Column(DateTime, default=datetime.utcnow)

    note = relationship("Note")


# ── 题目解析 ──

def parse_questions(markdown_content: str) -> list[dict]:
    """从 markdown 中解析出单个题目

    支持两种格式：
    - 新格式: ### Q1. 题目标题 ... (用 --- 分隔)
    - 旧格式: **Q1: 题目标题** ... (题目直接连续)
    """
    if not markdown_content:
        return []

    questions = []

    # 尝试新格式：按 --- 分割
    blocks = re.split(r'\n---\s*\n', markdown_content)

    # 检测是否是新格式（多个 block 且每个含 ### Q）
    new_format = sum(1 for b in blocks if re.search(r'###\s*Q\d', b)) > 1

    if new_format:
        idx = 1
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            m = re.search(r'###\s*Q(\d+)[.:：]\s*(.+)', block)
            if not m:
                continue
            num = int(m.group(1))
            title = m.group(2).strip()
            q = _parse_question_fields(block, num, title, idx)
            if q:
                questions.append(q)
                idx += 1
    else:
        # 旧格式：按 **Q\d+:** 分割
        # 先找到所有 **Q\d+:** 的位置
        pattern = r'\*\*Q(\d+)[.:：]\s*(.+?)\*\*'
        matches = list(re.finditer(pattern, markdown_content))

        for i, m in enumerate(matches):
            num = int(m.group(1))
            title = m.group(2).strip()
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_content)
            block = markdown_content[start:end]
            q = _parse_question_fields(block, num, title, i + 1)
            if q:
                questions.append(q)

    return questions


def _parse_question_fields(block: str, num: int, title: str, idx: int) -> dict:
    """从题目文本块中提取各字段"""
    # 提取难度
    diff_match = re.search(r'\*\*难度\*\*[：:]\s*(.+)', block)
    difficulty = diff_match.group(1).strip() if diff_match else ""

    # 提取分类
    cat_match = re.search(r'\*\*分类\*\*[：:]\s*(.+)', block)
    category = cat_match.group(1).strip() if cat_match else ""

    # 提取知识点（新格式）或 关联知识点（旧格式）
    kp_match = re.search(r'\*\*(?:知识点|关联知识点)\*\*[：:]\s*(.+)', block)
    knowledge = kp_match.group(1).strip() if kp_match else ""

    # 提取答案
    answer = ""
    # 新格式：**标准答案**: 后跟内容
    ans_match = re.search(
        r'\*\*(?:标准)?答案\*\*[：:]\s*\n?([\s\S]*?)'
        r'(?=\n\*\*(?:代码示例|评分标准|扩展追问|难度|分类|知识点|考察重点|出题意图)\*\*|\n---|\Z)',
        block,
    )
    if ans_match:
        answer = ans_match.group(1).strip()

    return {
        "index": idx,
        "num": num,
        "title": title,
        "difficulty": difficulty,
        "category": category,
        "knowledge": knowledge,
        "answer": answer,
        "full_text": block,
    }


# ── 自测记录 CRUD ──

def save_quiz_record(note_id: int, question_index: int, mastered: bool):
    with get_session() as session:
        # 先删除同一条旧记录
        session.query(QuizRecord).filter_by(
            note_id=note_id, question_index=question_index
        ).delete()
        record = QuizRecord(
            note_id=note_id,
            question_index=question_index,
            mastered=mastered,
        )
        session.add(record)
        session.commit()


def get_quiz_records(note_id: int) -> dict[int, bool]:
    """返回 {question_index: mastered}"""
    with get_session() as session:
        records = session.query(QuizRecord).filter_by(note_id=note_id).all()
        return {r.question_index: r.mastered for r in records}


def reset_quiz_records(note_id: int):
    with get_session() as session:
        session.query(QuizRecord).filter_by(note_id=note_id).delete()
        session.commit()


# ── 数据库初始化 ──
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},  # NiceGUI 多线程访问
        )
        Base.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    return Session(get_engine())


# ── 便捷 CRUD ──

def create_note(date: str, raw_notes: str, job_position: str) -> Note:
    with get_session() as session:
        note = Note(date=date, raw_notes=raw_notes, job_position=job_position)
        session.add(note)
        session.commit()
        session.refresh(note)
        return note


def update_note_status(note_id: int, status: str, error_msg: str = ""):
    with get_session() as session:
        note = session.query(Note).filter_by(id=note_id).first()
        if note:
            note.status = status
            if error_msg:
                note.error_msg = error_msg
            session.commit()


def save_questions(note_id: int, content: str, question_count: int, difficulty: str = ""):
    with get_session() as session:
        q = InterviewQuestion(
            note_id=note_id,
            content=content,
            question_count=question_count,
            difficulty_distribution=difficulty,
        )
        session.add(q)
        session.commit()


def get_all_notes(limit: int = 50) -> list:
    with get_session() as session:
        return (
            session.query(Note)
            .options(selectinload(Note.questions))
            .order_by(Note.created_at.desc())
            .limit(limit)
            .all()
        )


# ── 简单内存缓存：get_all_notes 2秒内不重复查库 ──
_notes_cache: list | None = None
_notes_cache_time: float = 0
_NOTES_CACHE_TTL = 2.0


def get_notes_cached(limit: int = 50) -> list:
    global _notes_cache, _notes_cache_time
    now = time.time()
    if _notes_cache is not None and (now - _notes_cache_time) < _NOTES_CACHE_TTL:
        return _notes_cache
    _notes_cache = get_all_notes(limit)
    _notes_cache_time = now
    return _notes_cache


def invalidate_notes_cache():
    """写入数据后调用，使缓存失效"""
    global _notes_cache, _notes_cache_time
    _notes_cache = None
    _notes_cache_time = 0


def get_note_by_id(note_id: int) -> Optional[Note]:
    with get_session() as session:
        return session.query(Note).filter_by(id=note_id).first()


def get_questions_by_note_id(note_id: int) -> Optional[InterviewQuestion]:
    with get_session() as session:
        return (
            session.query(InterviewQuestion)
            .filter_by(note_id=note_id)
            .order_by(InterviewQuestion.created_at.desc())
            .first()
        )


def save_knowledge_graph(note_id: int, graph_data: str):
    """保存知识图谱 JSON 数据"""
    with get_session() as session:
        # 先删除旧的
        session.query(KnowledgeGraph).filter_by(note_id=note_id).delete()
        kg = KnowledgeGraph(note_id=note_id, graph_data=graph_data)
        session.add(kg)
        session.commit()


def get_knowledge_graph(note_id: int) -> Optional[str]:
    """获取知识图谱 JSON 数据"""
    with get_session() as session:
        kg = (
            session.query(KnowledgeGraph)
            .filter_by(note_id=note_id)
            .order_by(KnowledgeGraph.created_at.desc())
            .first()
        )
        return kg.graph_data if kg else None


def delete_note(note_id: int):
    with get_session() as session:
        note = session.query(Note).filter_by(id=note_id).first()
        if note:
            session.delete(note)
            session.commit()


# ── 面试题导入 ──

def import_questions_from_markdown(file_content: str, filename: str = "") -> tuple:
    """从 markdown 文件导入面试题到数据库

    Args:
        file_content: markdown 文件内容
        filename: 文件名（用于提取日期和岗位）

    Returns:
        (success: bool, message: str, question_count: int)
    """
    # 1. 从文件名提取日期和岗位
    date_str = ""
    job_position = "未知岗位"
    if filename:
        # 匹配格式: 面试题_2026-05-22_AI大模型开发工程师.md
        m = re.match(r'面试题[_\s]*(\d{4}-\d{2}-\d{2})[_\s]*(.+?)\.md$', filename)
        if m:
            date_str = m.group(1)
            job_position = m.group(2).strip()

    # 如果文件名没匹配到，尝试从内容中提取日期
    if not date_str:
        m = re.search(r'(\d{4}-\d{2}-\d{2})', file_content)
        date_str = m.group(1) if m else datetime.now().strftime("%Y-%m-%d")

    # 2. 解析题目
    questions = parse_questions(file_content)
    if not questions:
        return False, "未解析到有效面试题，请检查文件格式", 0

    # 3. 检查是否已导入（按 date + job_position 去重）
    with get_session() as session:
        existing = session.query(Note).filter_by(
            date=date_str, job_position=job_position, status="done"
        ).first()
        if existing:
            return False, f"已有相同记录：{date_str} | {job_position}", len(questions)

    # 4. 创建 Note + InterviewQuestion 记录
    note = create_note(
        date=date_str,
        raw_notes=file_content,
        job_position=job_position,
    )
    update_note_status(note.id, "done")
    save_questions(
        note_id=note.id,
        content=file_content,
        question_count=len(questions),
    )
    invalidate_notes_cache()

    return True, f"导入成功：{date_str} | {job_position} | {len(questions)} 题", len(questions)
