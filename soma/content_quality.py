"""内容质量检测 — 评估外部知识的文本质量与可信度

纯本地启发式指标（零 LLM、零网络）：
  - 信息密度: 去停用词后的有效词占比，过滤空话套话
  - 重复率:   n-gram 重复占比，过滤啰嗦/复制粘贴
  - 营销密度: 广告/促销词命中，过滤营销内容
  - 噪音检测: 感叹号密度、纯符号段、过短内容

可选 LLM 增强（v2.0.9）: 当传入带 LLM 能力的 agent 时，用 LLM 对内容
质量/事实合理性做二次评估；失败或未配置时自动回退纯本地分。

设计原则：纯本地指标保证零成本兜底，LLM 增强仅在有 key 时生效。
"""
import re
from typing import Any, Dict, Optional

# 停用词（中文常用虚词/语气词）
_STOP_WORDS = set("""
的 了 和 是 在 我 有 也 就 不 人 都 一 一个 上 很 会 这 那 吗 呢 吧 啊
的 地 得 与 及 或 而 并 且 但 却 还 已 更 最 太 真 好 被 把 让 给
我们 你们 他们 它们 这个 那个 这些 那些 这样 那样 什么 怎么 为什么 如何
可以 能够 应该 需要 可能 就是 只是 但是 因为 所以 如果 那么 然后 接着
觉得 东西 怎么 反正 很好 很棒 非常 大家 应该 知道 这样 那个 就是
其实 真的 确实 好像 感觉 大概 也许 总之 就是 然后 特别 非常 超级 棒
""".split())

# 空话/套话词库 — 高密度命中视为低信息量
_FLUFF_WORDS = (
    "我觉得", "怎么说", "反正", "挺好的", "很棒", "非常好", "很厉害",
    "大家都知道", "毫无疑问", "众所周知", "总而言之", "一般来说",
    "我个人认为", "在我看来", "某种程度上", "某种意义上", "值得注意的是",
)

# 营销/低质词库
_MARKETING_WORDS = (
    "限时", "抢购", "促销", "优惠", "点击", "免费", "立即", "速来", "错过",
    "震惊", "必看", "火爆", "疯抢", "全场", "秒杀", "红包", "返现", "升级",
    "独家", "唯一", "第一", "最强", "最佳", "绝对", "百分百", "保证",
    "hurry", "limited", "free", "click", "buy now", "act now", "discount",
    "amazing", "incredible", "best", "guaranteed",
)
# 感叹号/震惊阈值
_EXCLAIM_MAX_RATIO = 0.05
# 最短有效内容（字符）
_MIN_VALID_LENGTH = 15


def _info_density(text: str) -> float:
    """信息密度 = 有效词数 / 总词数。去停用词后的词占比越高越有信息量。"""
    tokens = re.findall(r"[一-鿿]{2,}|[a-zA-Z]{3,}", text)
    if not tokens:
        return 0.0
    effective = [t for t in tokens if t not in _STOP_WORDS]
    return round(len(effective) / max(len(tokens), 1), 3)


def _repetition_ratio(text: str) -> float:
    """n-gram 重复率：bigram 重复占比越高越啰嗦。"""
    tokens = re.findall(r"[一-鿿]|[a-zA-Z]+", text.lower())
    if len(tokens) < 6:
        return 0.0
    bigrams = list(zip(tokens, tokens[1:]))
    total = len(bigrams)
    if total == 0:
        return 0.0
    unique = len(set(bigrams))
    return round(max(0, 1.0 - unique / total), 3)


def _marketing_density(text: str) -> float:
    """营销词密度：命中营销词库的比例。"""
    lowered = text.lower()
    hits = sum(1 for w in _MARKETING_WORDS if w.lower() in lowered)
    return round(min(hits / 5.0, 1.0), 3)


def _fluff_ratio(text: str) -> float:
    """空话/套话词命中率：命中空话词库比例越高越像空话。"""
    lowered = text.lower()
    hits = sum(1 for w in _FLUFF_WORDS if w.lower() in lowered)
    return round(min(hits / 3.0, 1.0), 3)


def _noise_score(text: str) -> float:
    """噪音分：感叹号密度 + 符号比例。分越低越干净。"""
    exclaim = text.count("!") + text.count("！")
    exclaim_ratio = exclaim / max(len(text), 1)
    # 纯符号比例
    alpha_chars = len(re.findall(r"[一-鿿 a-zA-Z]", text))
    symbol_ratio = 1.0 - alpha_chars / max(len(text), 1)
    score = min(exclaim_ratio / _EXCLAIM_MAX_RATIO, 1.0) * 0.5 + symbol_ratio * 0.5
    return round(min(score, 1.0), 3)


def assess_content_quality(text: str, agent: Optional[Any] = None,
                           use_llm: bool = False) -> Dict[str, Any]:
    """评估文本内容质量。

    Args:
        text: 外部内容文本
        agent: 可选 SOMA_Agent（提供 LLM 能力）
        use_llm: 是否尝试 LLM 增强（有 key 且 use_llm 时）

    Returns:
        {"score": 0-1, "metrics": {...}, "llm_used": bool, "llm_reason": ""}
    """
    if not text or len(text.strip()) < _MIN_VALID_LENGTH:
        return {
            "score": 0.0, "metrics": {"too_short": True},
            "llm_used": False, "llm_reason": "内容过短",
        }

    metrics = {
        "info_density": _info_density(text),
        "repetition_ratio": _repetition_ratio(text),
        "marketing_density": _marketing_density(text),
        "noise_score": _noise_score(text),
        "fluff_ratio": _fluff_ratio(text),
    }

    # 纯本地综合分：信息密度权重最高，重复/营销/噪音/空话为惩罚项
    score = (
        metrics["info_density"] * 0.45
        + (1.0 - metrics["repetition_ratio"]) * 0.15
        + (1.0 - metrics["marketing_density"]) * 0.20
        + (1.0 - metrics["noise_score"]) * 0.10
        + (1.0 - metrics["fluff_ratio"]) * 0.10
    )
    # 强惩罚：营销或噪音过高时额外降权（营销权重最大，避免垃圾内容混入）
    if metrics["marketing_density"] > 0.6:
        score *= 0.4
    if metrics["noise_score"] > 0.5:
        score *= 0.8
    if metrics["fluff_ratio"] > 0.3:
        score *= 0.8
    score = round(max(0.0, min(1.0, score)), 3)

    result = {
        "score": score,
        "metrics": metrics,
        "llm_used": False,
        "llm_reason": "",
    }

    # 可选 LLM 增强
    if use_llm and agent is not None and hasattr(agent, "_call_llm"):
        try:
            prompt = (
                "评估以下外部内容的质量与事实合理性，输出 JSON:\n"
                '{"quality": 0-1, "is_factual": true/false, "reason": "一句话理由"}\n'
                f"内容:\n{text[:800]}"
            )
            resp = agent._call_llm(prompt, "")
            import json as _json
            parsed = _extract_json(resp)
            if parsed and "quality" in parsed:
                llm_q = float(parsed["quality"])
                # LLM 分与本地分各占 50%
                result["score"] = round((score + llm_q) / 2, 3)
                result["llm_used"] = True
                result["llm_reason"] = str(parsed.get("reason", ""))[:200]
                if parsed.get("is_factual") is False:
                    # 事实性存疑，整体降权 20%
                    result["score"] = round(result["score"] * 0.8, 3)
        except Exception:
            pass  # LLM 失败回退本地分

    return result


def _extract_json(text: str) -> Optional[Dict]:
    """从 LLM 响应中提取 JSON 对象（容忍前后文噪声）。"""
    import json
    if not text:
        return None
    # 尝试直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 匹配第一个 { ... } 块
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None
