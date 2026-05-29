"""LLM 客户端 — 支持 OpenAI / Claude API 直接调用"""
import json
import logging
import time
from typing import Callable, Optional

import httpx
from openai import OpenAI

from config import settings

logger = logging.getLogger(__name__)

# NVIDIA API 网关超时约 5 分钟，留余量
API_TIMEOUT = 240  # 单次请求超时（秒）
MAX_INPUT_CHARS = 30000  # 输入最大字符数，防止 504


def _truncate(text: str, limit: int = MAX_INPUT_CHARS) -> str:
    """截断过长的输入文本"""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    logger.warning("输入文本过长（%d 字符），已截断至 %d", len(text), limit)
    return truncated + "\n\n...（内容过长，已截断）"


class LLMClient:
    """统一的 LLM 调用客户端"""

    def __init__(self):
        timeout = httpx.Timeout(API_TIMEOUT, connect=30.0)
        if settings.AI_ENGINE == "claude":
            self.client = OpenAI(
                api_key=settings.CLAUDE_API_KEY,
                base_url=settings.CLAUDE_BASE_URL,
                timeout=timeout,
                max_retries=2,
            )
            self.model = settings.CLAUDE_MODEL
        else:
            self.client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                timeout=timeout,
                max_retries=2,
            )
            self.model = settings.OPENAI_MODEL

    def chat(self, system: str, user: str, temperature: float = 0.7, max_tokens: int = 4000) -> str:
        """单轮对话调用"""
        user = _truncate(user)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    def chat_stream(self, system: str, user: str, temperature: float = 0.7, max_tokens: int = 4000):
        """流式调用，逐块 yield 文本"""
        user = _truncate(user)
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content


# ── Prompt 模板 ──

SYSTEM_PREPROCESS = """你是一位专业的技术笔记整理专家。

## 任务
将用户提供的学习笔记进行智能清洗和结构化整理。

## 处理步骤
1. **去噪**：删除广告、无关链接、重复内容
2. **分类**：自动识别技术模块（框架、算法、数据库、网络等）
3. **提取**：提炼核心概念、原理、优缺点、应用场景
4. **关联**：标注模块间的前置/依赖/扩展关系
5. **规范化**：统一代码块格式，标注编程语言

## 输出格式

# 整理后的学习笔记

## 知识模块清单

### 模块1：[模块名称]
- **核心概念**：[简明定义]
- **技术原理**：[原理说明]
- **关键特性**：优点/缺点
- **应用场景**：[适用场景]
- **关联知识**：[前置] → [当前] → [扩展]
- **代码示例**：
  ```语言
  [代码]
  ```

### 模块2：[模块名称]
[同上结构]

## 难点与易错点
- ...

## 实践心得
- ...

## 知识盲区
- [ ] [待学习内容]

## 要求
- 每个模块必须有实际内容
- 代码必须可运行且有注释
- 不要遗漏原始笔记中的重要知识点"""


SYSTEM_KNOWLEDGE_GRAPH = """你是一位知识图谱构建专家。

根据整理后的学习笔记，提取所有知识点实体及其关系。

## 输出格式（仅输出 JSON，不要其他内容）

{
  "knowledge_points": [
    {"id": "kp_001", "name": "知识点名称", "category": "技术分类", "difficulty": "基础/进阶/高级", "importance": "高/中/低"}
  ],
  "relationships": [
    {"source": "kp_001", "target": "kp_002", "relation": "前置/依赖/关联/包含/扩展"}
  ],
  "weak_areas": [
    {"topic": "薄弱知识点", "reason": "原因", "suggestion": "建议"}
  ]
}"""


SYSTEM_INTERVIEW_GEN = """你是一位顶级{position}面试官，拥有10年以上大厂面试经验。

根据整理后的笔记和知识图谱，生成 8-12 道高质量面试题。

## 难度分布
- 基础题（3-4道）：核心概念理解，难度 ⭐⭐
- 进阶题（3-4道）：源码理解、设计思想，难度 ⭐⭐⭐
- 项目题（2-3道）：场景应用、方案设计，难度 ⭐⭐⭐⭐
- 综合题（1-2道）：系统思维、架构能力，难度 ⭐⭐⭐⭐⭐

## 每道题格式

### Q[N]. [题目]
- **难度**: ⭐⭐⭐
- **分类**: 基础/进阶/项目/综合
- **知识点**: [标签]
- **考察重点**: [核心能力]
- **出题意图**: [与岗位的关联]

**标准答案**:
[详细答案]

**代码示例**:
```语言
[可运行的代码，带注释]
```

**评分标准**:
- 满分要点：[3-5个得分点]
- 常见扣分：[常见错误]

**扩展追问**:
- 追问1: [深入追问]
- 追问2: [跨领域追问]

---

## 质量红线
1. 题目必须有实际面试价值，禁止凑数题
2. 答案必须准确，代码必须可运行
3. 每道题必须有代码示例（基础概念题除外）
4. 扩展追问能引导深度思考
5. 覆盖笔记中80%以上核心知识点
6. 参考字节跳动、阿里巴巴等大厂面试风格"""


SYSTEM_QUALITY_REVIEW = """你是一位面试题质量审核专家。

## 任务
审查面试题，进行质量把关。

## 审查维度
1. **准确性**：答案是否正确，代码是否可运行
2. **完整性**：是否包含所有必要元素
3. **区分度**：难度标注是否合理
4. **去重**：是否有重复或高度相似的题目
5. **覆盖面**：知识点覆盖是否全面

## 处理规则
- 发现错误 → 直接修正
- 发现重复 → 保留更好的，删除重复的
- 发现不完整 → 补充缺失部分
- 难度不合理 → 修正

## 输出修正后的完整面试题，保持原有格式"""


SYSTEM_EXTENSION = """你是一位{position}深度练习教练。

根据知识图谱中的薄弱环节，生成 3-5 道补充练习题。

## 出题策略
1. 优先针对薄弱环节出题
2. 覆盖岗位需要但候选人不熟的能力差距领域
3. 题目有梯度，逐步深入

## 每道题格式

### 补充题[N]. [题目]
- **针对薄弱点**: [关联知识点]
- **难度**: ⭐⭐⭐⭐~⭐⭐⭐⭐⭐
- **练习目标**: [提升的能力]

**引导思路**:
[启发思考，不直接给答案]

**参考答案**:
[详细答案]

**延伸阅读建议**:
- [学习资源方向]

## 要求
1. 难度高于主面试题
2. 重点考察深度理解
3. 每道题有实际应用场景"""


SYSTEM_FINAL_COMPILE = """你是一位 Markdown 文档排版专家。

将面试题和补充题整合为一份完整的、格式优美的 Markdown 文档。

## 输出格式

# 面试题集 - {position} - {date}

> 基于当日学习笔记自动生成

---

## 一、面试题（主考题）

[质量审查后的面试题]

---

## 二、深度练习题（补充题）

[扩展追问生成的补充题]

---

## 三、学习建议

### 今日学习总结
- [简要总结覆盖的知识领域]

### 重点复习方向
- [基于薄弱环节的复习建议]

---

*本面试题由 AI 自动生成 | 仅供参考学习使用*

## 要求
1. 保持原始内容不变
2. 统一 Markdown 格式，代码块有语言标注
3. 输出完整文档，不要截断"""


# ── 生成流水线 ──

STREAM_THROTTLE = 0.5  # 流式 UI 更新最小间隔（秒）


def _stream_chat(client: LLMClient, system: str, user: str,
                 accumulated: list, on_stream: Optional[Callable],
                 prev_len: int, **kwargs) -> str:
    """流式调用单个步骤，实时推送内容（节流更新）"""
    chunks = []
    last_update = 0.0
    for chunk in client.chat_stream(system=system, user=user, **kwargs):
        chunks.append(chunk)
        accumulated[0] += chunk
        if on_stream:
            now = time.time()
            if now - last_update >= STREAM_THROTTLE:
                on_stream(accumulated[0])
                last_update = now
    # 最后一次更新确保内容完整
    if on_stream:
        on_stream(accumulated[0])
    return "".join(chunks)


def run_pipeline(client: LLMClient, raw_notes: str, position: str, date: str,
                 progress_callback=None, on_stream: Optional[Callable] = None,
                 on_step: Optional[Callable] = None) -> dict:
    """完整的面试题生成流水线（支持流式 + 自动重试）

    Args:
        client: LLM 客户端
        raw_notes: 原始笔记
        position: 目标岗位
        date: 日期
        progress_callback: 进度回调 fn(percent, msg)
        on_stream: 流式回调 fn(accumulated_content)
        on_step: 步骤切换回调 fn(step_index, step_label)

    Returns:
        {"output": str, "question_count": int}
    """
    MAX_RETRIES = 3

    def _progress(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    def _step(idx, label):
        if on_step:
            on_step(idx, label)

    accumulated = [""]
    use_stream = on_stream is not None

    def _call(system, user, label, step_idx, **kwargs):
        """调用单个步骤，失败自动重试，重试时从断点继续"""
        _step(step_idx, label)
        if not use_stream:
            return client.chat(system=system, user=user, **kwargs)

        # 流式模式
        header = f"\n\n---\n\n## {label}\n\n"
        save_len = len(accumulated[0])
        accumulated[0] += header
        on_stream(accumulated[0])

        for attempt in range(MAX_RETRIES):
            try:
                return _stream_chat(
                    client, system, user, accumulated, on_stream, save_len, **kwargs,
                )
            except Exception as e:
                logger.warning("步骤 '%s' 第 %d/%d 次失败: %s", label, attempt + 1, MAX_RETRIES, e)
                if attempt + 1 >= MAX_RETRIES:
                    raise
                # 重试：截断到步骤开始前，重新加 header
                time.sleep(2)
                accumulated[0] = accumulated[0][:save_len] + header
                on_stream(accumulated[0])

    # Step 1: 笔记预处理
    _progress(5, "正在整理笔记...")
    logger.info("Step 1: 笔记预处理")
    cleaned_notes = _call(
        SYSTEM_PREPROCESS, f"学习日期：{date}\n\n{raw_notes}",
        "笔记整理", 1, temperature=0.3, max_tokens=4000,
    )

    # Step 2: 知识图谱构建
    _progress(20, "构建知识图谱...")
    logger.info("Step 2: 知识图谱构建")
    knowledge_graph = _call(
        SYSTEM_KNOWLEDGE_GRAPH, cleaned_notes,
        "知识图谱构建", 2, temperature=0.1, max_tokens=2000,
    )

    # Step 3: 面试题生成
    _progress(40, "正在生成面试题...")
    logger.info("Step 3: 面试题生成")
    system_gen = SYSTEM_INTERVIEW_GEN.replace("{position}", position)
    interview_questions = _call(
        system_gen, f"## 整理后的笔记\n\n{cleaned_notes}\n\n## 知识图谱\n\n{knowledge_graph}",
        "面试题生成", 3, temperature=0.7, max_tokens=8000,
    )

    # Step 4: 质量审查
    _progress(65, "质量审查中...")
    logger.info("Step 4: 质量审查")
    reviewed = _call(
        SYSTEM_QUALITY_REVIEW, interview_questions,
        "质量审查", 4, temperature=0.1, max_tokens=8000,
    )

    # Step 5: 扩展追问
    _progress(80, "生成补充练习题...")
    logger.info("Step 5: 扩展追问")
    system_ext = SYSTEM_EXTENSION.replace("{position}", position)
    try:
        extension = _call(
            system_ext, knowledge_graph,
            "补充练习题", 5, temperature=0.7, max_tokens=3000,
        )
    except Exception:
        extension = ""

    # Step 6: 最终整合
    _progress(90, "整合输出...")
    logger.info("Step 6: 最终整合")
    system_final = SYSTEM_FINAL_COMPILE.replace("{position}", position).replace("{date}", date)
    final_input = f"## 质量审查后的面试题\n\n{reviewed}"
    if extension:
        final_input += f"\n\n## 扩展追问/补充题\n\n{extension}"

    _step(6, "最终整合")
    output = client.chat(
        system=system_final,
        user=final_input,
        temperature=0.1,
        max_tokens=8000,
    )
    if use_stream:
        accumulated[0] = output
        on_stream(accumulated[0])

    # 统计题目数量
    question_count = output.count("**Q") + output.count("补充题")

    _progress(100, "生成完成！")
    logger.info("流水线完成: %d 道题", question_count)

    return {
        "output": output,
        "question_count": question_count,
        "knowledge_graph": knowledge_graph,
    }
