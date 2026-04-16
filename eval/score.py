"""
Agent 评测评分器

计算三个维度的分数：
  1. JD 关键词匹配率提升（客观指标）
  2. 工具调用正确性（自动断言）
  3. LLM-as-Judge 质量评分

用法：
    cd backend
    uv run python ../eval/score.py --input eval_results.json [--output eval_scores.json]
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
EVAL_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.llm.chat_service import ChatService  # noqa: E402


TOOL_NAME_ALIASES = {
    "优化简介": "update_overview",
    "优化成果": "update_highlight",
    "新增成果": "add_highlight",
    "删除成果": "remove_highlight",
    "读取简历": "read_resume",
}


def _count_question_marks(text: str) -> int:
    return text.count("?") + text.count("？")


def score_decision_rule(result: dict) -> dict:
    """对 optimize-first 决策规则做定向评分。"""
    case = result["case"]
    expected = case.get("expected_decision")
    if not expected:
        return {"skipped": True, "reason": "no decision expectation"}

    reply = (result.get("agent_reply") or "").strip()
    actual_tool_calls = result.get("tool_calls") or []
    has_tool_call = len(actual_tool_calls) > 0
    forbidden = case.get("forbidden_reply_substrings", [])
    required_any = case.get("required_reply_substrings_any", [])
    max_q = case.get("max_question_marks")

    hit_forbidden = [s for s in forbidden if s and s in reply]
    hit_required_any = [s for s in required_any if s and s in reply]
    question_marks = _count_question_marks(reply)

    if expected == "execute":
        correct = has_tool_call and not hit_forbidden
        return {
            "expected": expected,
            "actual": "execute" if has_tool_call else "clarify_or_reply",
            "correct": correct,
            "score": 1.0 if correct else 0.0,
            "has_tool_call": has_tool_call,
            "forbidden_hits": hit_forbidden,
        }

    if expected == "clarify":
        clarify_shape_ok = not has_tool_call
        specific_enough = True if not required_any else bool(hit_required_any)
        concise_enough = True if max_q is None else question_marks <= max_q
        correct = clarify_shape_ok and specific_enough and concise_enough and not hit_forbidden
        return {
            "expected": expected,
            "actual": "execute" if has_tool_call else "clarify_or_reply",
            "correct": correct,
            "score": 1.0 if correct else 0.0,
            "has_tool_call": has_tool_call,
            "required_any_hits": hit_required_any,
            "forbidden_hits": hit_forbidden,
            "question_marks": question_marks,
            "max_question_marks": max_q,
        }

    return {"skipped": True, "reason": f"unknown expected_decision={expected}"}


# ─────────────────────────────────────────────────────────────
# 1. JD 关键词匹配率
# ─────────────────────────────────────────────────────────────

def _resume_text(resume: dict) -> str:
    """将简历结构体展平为纯文本，用于关键词匹配。"""
    parts = []

    def collect(obj):
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, list):
            for item in obj:
                collect(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                collect(v)

    collect(resume)
    return " ".join(parts).lower()


def keyword_match_rate(resume: dict, keywords: list[str]) -> float:
    """返回关键词覆盖率 [0, 1]。"""
    if not keywords:
        return 0.0
    text = _resume_text(resume)
    matched = sum(1 for kw in keywords if kw.lower() in text)
    return round(matched / len(keywords), 3)


def score_keyword_improvement(result: dict) -> dict:
    """计算单个用例的关键词匹配率提升。"""
    case = result["case"]
    jd_file = case.get("jd_file")
    if not jd_file:
        return {"skipped": True, "reason": "no JD"}

    jd_path = EVAL_DIR / "cases" / jd_file
    with open(jd_path) as f:
        jd = json.load(f)
    keywords = jd.get("keywords", [])

    before = keyword_match_rate(result["resume_before"], keywords)
    after = keyword_match_rate(result["resume_after"], keywords)
    delta = round(after - before, 3)

    return {
        "before": before,
        "after": after,
        "delta": delta,
        "keywords_total": len(keywords),
        "improved": delta > 0,
    }


# ─────────────────────────────────────────────────────────────
# 2. 工具调用正确性
# ─────────────────────────────────────────────────────────────

def score_tool_correctness(result: dict) -> dict:
    """检查 Agent 实际调用的工具是否符合预期。"""
    case = result["case"]
    expected = set(case.get("expected_tool_calls", []))
    actual = {
        TOOL_NAME_ALIASES.get(name, name)
        for name in result.get("tool_calls", [])
    }

    if not expected:
        # 用例期望无工具调用
        correct = len(actual) == 0
        return {
            "expected": list(expected),
            "actual": list(actual),
            "correct": correct,
            "score": 1.0 if correct else 0.0,
            "note": "期望无工具调用" if correct else f"意外调用了: {actual}",
        }

    # 计算交集覆盖率
    hit = expected & actual
    precision = len(hit) / len(actual) if actual else 0.0
    recall = len(hit) / len(expected)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "expected": list(expected),
        "actual": list(actual),
        "hit": list(hit),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "score": round(f1, 3),
    }


# ─────────────────────────────────────────────────────────────
# 3. LLM-as-Judge
# ─────────────────────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """你是一名专业的简历优化评审官。
你的任务是评估 AI 简历优化 Agent 的输出质量。
请严格按照 JSON 格式返回评分，不要添加任何额外的文字说明。"""

JUDGE_USER_TEMPLATE = """请评估以下 Agent 的简历优化表现：

【用户指令】
{user_message}

【Agent 回复】
{agent_reply}

【修改前简历摘要】
{resume_before_summary}

【修改后简历摘要】
{resume_after_summary}

【工具调用记录】
{tool_calls}

请从以下三个维度打分（1-5分），并给出简短理由：

1. instruction_follow（指令遵循度）：Agent 是否准确理解并执行了用户指令？
2. quality（内容质量）：优化后的内容是否专业、清晰、有说服力？
3. no_hallucination（无幻觉）：Agent 是否只基于用户现有经历优化，未捏造事实？

返回格式（严格 JSON）：
{{
  "instruction_follow": {{"score": 1-5, "reason": "..."}},
  "quality": {{"score": 1-5, "reason": "..."}},
  "no_hallucination": {{"score": 1-5, "reason": "..."}},
  "overall": 1-5
}}"""


def _summarize_resume(resume: dict, max_chars: int = 400) -> str:
    """生成简历摘要，用于 LLM-as-Judge 提示。"""
    def normalize_highlights(highlights) -> list[str]:
        values = []
        for item in (highlights or [])[:2]:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("text", "")).strip()
            else:
                text = str(item).strip()
            if text:
                values.append(text)
        return values

    lines = []
    pi = resume.get("personal_info", {})
    if pi.get("name"):
        lines.append(f"姓名: {pi['name']}")

    for exp in (resume.get("work_experience") or [])[:2]:
        highlights = normalize_highlights(exp.get("highlights", []))
        lines.append(f"工作: {exp.get('company', '')} - {'; '.join(highlights)}")

    for proj in (resume.get("projects") or [])[:2]:
        highlights = normalize_highlights(proj.get("highlights", []))
        lines.append(f"项目: {proj.get('name', '')} - {'; '.join(highlights)}")

    text = "\n".join(lines)
    return text[:max_chars] if len(text) > max_chars else text


async def llm_judge_single(chat_service: ChatService, result: dict) -> dict:
    """使用 LLM 对单个用例打分。"""
    if result["status"] != "ok" or not result.get("agent_reply"):
        return {"skipped": True, "reason": result.get("error", "no reply")}

    case = result["case"]
    prompt = JUDGE_USER_TEMPLATE.format(
        user_message=case["user_message"],
        agent_reply=result["agent_reply"][:600],
        resume_before_summary=_summarize_resume(result["resume_before"]),
        resume_after_summary=_summarize_resume(result["resume_after"]),
        tool_calls=", ".join(result["tool_calls"]) or "无",
    )

    try:
        raw = await chat_service.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
            system_prompt=JUDGE_SYSTEM_PROMPT,
        )

        def extract_text(payload) -> str:
            if isinstance(payload, str):
                return payload
            if isinstance(payload, dict):
                choices = payload.get("choices")
                if isinstance(choices, list) and choices:
                    first = choices[0]
                    if isinstance(first, dict):
                        message = first.get("message")
                        if isinstance(message, dict):
                            content = message.get("content")
                            if isinstance(content, str):
                                return content
                        text = first.get("text")
                        if isinstance(text, str):
                            return text
                content = payload.get("content")
                if isinstance(content, str):
                    return content
            return str(payload)

        # 提取 JSON
        text = extract_text(raw)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return {"skipped": True, "reason": "LLM 未返回 JSON"}
        scores = json.loads(text[start:end])
        return {"skipped": False, "scores": scores}
    except Exception as e:
        return {"skipped": True, "reason": str(e)}


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────

async def score_all(results: list[dict], enable_llm_judge: bool = True) -> list[dict]:
    chat_service = ChatService() if enable_llm_judge else None
    scored = []

    print(f"\n{'='*60}")
    print(f"评分 {len(results)} 个结果")
    print(f"{'='*60}\n")

    for i, result in enumerate(results, 1):
        rid = result["id"]
        print(f"[{i}/{len(results)}] {rid} - {result['desc']}")

        if result["status"] != "ok":
            print(f"  跳过（执行失败）\n")
            scored.append({**result, "scores": {"status": "error"}})
            continue

        kw_score = score_keyword_improvement(result)
        tool_score = score_tool_correctness(result)
        decision_score = score_decision_rule(result)

        judge_score = {"skipped": True, "reason": "disabled"}
        if enable_llm_judge and chat_service:
            judge_score = await llm_judge_single(chat_service, result)

        # 打印摘要
        if not kw_score.get("skipped"):
            delta = kw_score["delta"]
            sign = "+" if delta >= 0 else ""
            print(f"  关键词匹配率: {kw_score['before']:.1%} → {kw_score['after']:.1%} ({sign}{delta:.1%})")

        print(f"  工具调用: 期望={tool_score.get('expected')} 实际={tool_score.get('actual')} F1={tool_score.get('f1', tool_score.get('score', '?'))}")

        if not decision_score.get("skipped"):
            print(
                f"  决策规则: 期望={decision_score.get('expected')} "
                f"实际={decision_score.get('actual')} "
                f"score={decision_score.get('score')}"
            )

        if not judge_score.get("skipped") and "scores" in judge_score:
            s = judge_score["scores"]
            print(f"  LLM Judge: 指令遵循={s.get('instruction_follow',{}).get('score','?')} "
                  f"内容质量={s.get('quality',{}).get('score','?')} "
                  f"无幻觉={s.get('no_hallucination',{}).get('score','?')} "
                  f"综合={s.get('overall','?')}")
        print()

        scored.append({
            **result,
            "scores": {
                "keyword_improvement": kw_score,
                "tool_correctness": tool_score,
                "decision_rule": decision_score,
                "llm_judge": judge_score,
            },
        })

    return scored


def print_summary(scored: list[dict]):
    """打印汇总统计。"""
    ok_results = [r for r in scored if r["status"] == "ok"]
    if not ok_results:
        print("没有成功的用例。")
        return

    # 关键词提升
    kw_deltas = [
        r["scores"]["keyword_improvement"]["delta"]
        for r in ok_results
        if not r["scores"]["keyword_improvement"].get("skipped")
    ]

    # 工具正确性
    tool_scores = [
        r["scores"]["tool_correctness"]["score"]
        for r in ok_results
    ]

    # LLM Judge
    judge_overalls = [
        r["scores"]["llm_judge"]["scores"]["overall"]
        for r in ok_results
        if not r["scores"]["llm_judge"].get("skipped") and "scores" in r["scores"]["llm_judge"]
    ]

    # optimize-first 决策规则
    decision_scores = [
        r["scores"]["decision_rule"]["score"]
        for r in ok_results
        if not r["scores"]["decision_rule"].get("skipped")
    ]

    print("\n" + "="*60)
    print("📊 评测汇总")
    print("="*60)
    print(f"成功用例: {len(ok_results)}/{len(scored)}")

    if kw_deltas:
        avg_delta = sum(kw_deltas) / len(kw_deltas)
        improved = sum(1 for d in kw_deltas if d > 0)
        print(f"\n[1] JD 关键词匹配率提升")
        print(f"    平均提升: {avg_delta:+.1%}")
        print(f"    有提升的用例: {improved}/{len(kw_deltas)}")

    if tool_scores:
        avg_tool = sum(tool_scores) / len(tool_scores)
        print(f"\n[2] 工具调用正确性 (F1)")
        print(f"    平均 F1: {avg_tool:.3f}")

    if judge_overalls:
        avg_judge = sum(judge_overalls) / len(judge_overalls)
        print(f"\n[3] LLM-as-Judge 综合评分 (1-5)")
        print(f"    平均分: {avg_judge:.2f}")

    if decision_scores:
        avg_decision = sum(decision_scores) / len(decision_scores)
        passed = sum(1 for s in decision_scores if s >= 1.0)
        print(f"\n[4] optimize-first 决策规则")
        print(f"    平均分: {avg_decision:.3f}")
        print(f"    通过用例: {passed}/{len(decision_scores)}")

    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Agent 评测评分器")
    parser.add_argument("--input", default="eval_results.json", help="run_eval.py 的输出文件")
    parser.add_argument("--output", default="eval_scores.json", help="评分结果输出文件")
    parser.add_argument("--no-llm-judge", action="store_true", help="跳过 LLM-as-Judge 评分（节省费用）")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    results = data["results"]

    scored = asyncio.run(score_all(results, enable_llm_judge=not args.no_llm_judge))
    print_summary(scored)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"scored": scored}, f, ensure_ascii=False, indent=2)
    print(f"评分结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
