"""真实 token 用量记录 —— 保存 LLM provider 返回的 usage，供接入方计量与排障。

为什么需要：SOMA 核心此前不暴露 token usage，接入方的用量页
只能按「字符数 / 2」估算。估算值不能用于计费，也对不上 provider 账单。

本模块只做一件事：把 provider 返回的真实数字留下来，并交给需要它的人。

职责边界（刻意收窄）：
- 记录 prompt / completion / total token、模型名、用户、耗时、是否估算
- 进程内累积 + 可注册回调（接入方据此落自己的库、上报计费系统）
- 不算钱、不管额度、不做持久化 —— 计费是独立项目，SOMA 只负责上报用量

v2.0.19
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class TokenUsage:
    """单次 LLM 调用的真实用量。

    estimated 字段标记这串数字是 provider 给的（False）还是本地兜底估的（True）。
    计费只能信 False，所以这个标记必须一路带到接入方，不能被吞掉。
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    user_id: str = ""
    purpose: str = ""          # 调用来源：respond / causal_extraction / law_discovery ...
    latency_ms: int = 0
    estimated: bool = False    # True = provider 没返回 usage，本地按字符估算
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "user_id": self.user_id,
            "purpose": self.purpose,
            "latency_ms": self.latency_ms,
            "estimated": self.estimated,
            "timestamp": self.timestamp,
        }


def _as_int(value: Any) -> int:
    """provider 有时回 None 或字符串数字，统一收成 int。"""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def estimate_tokens(text: str) -> int:
    """字符数估算 token —— 只作兜底，结果必须标 estimated=True。

    中英混合粗算：CJK 字符约 1 字 1 token，其余约 4 字符 1 token。
    """
    if not text:
        return 0
    cjk = 0
    for ch in text:
        o = ord(ch)
        if 0x3000 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF or 0xFF00 <= o <= 0xFFEF:
            cjk += 1
    other = len(text) - cjk
    return max(1, cjk + other // 4)

def extract_usage(response: Any) -> Optional[TokenUsage]:
    """从 litellm / OpenAI 风格的响应对象里取 usage。

    取不到（响应没有 usage 字段）返回 None —— 由调用方决定要不要估算。
    对象属性（litellm ModelResponse）与 dict 两种形状都支持，
    因为经自定义 base_url / 代理时回包形状不统一。
    """
    if response is None:
        return None

    try:
        usage = getattr(response, "usage", None)
        model = getattr(response, "model", "") or ""
    except Exception:      # 某些代理层的惰性对象，属性访问本身会抛
        return None

    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
        model = response.get("model", "") or ""
    if usage is None:
        return None

    def pick(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    prompt = _as_int(pick(usage, "prompt_tokens"))
    completion = _as_int(pick(usage, "completion_tokens"))
    total = _as_int(pick(usage, "total_tokens"))
    if prompt == 0 and completion == 0 and total == 0:
        return None          # 全零视为 provider 没给真实用量

    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        model=str(model),
        estimated=False,
    )


class UsageRecorder:
    """线程安全的用量累积器 + 回调分发。

    多专家编排下 LLM 调用来自多个线程（v1.1.0 的 ThreadPoolExecutor），
    所以计数走锁；回调在锁外执行，避免接入方在回调里做慢事拖住所有线程。
    """

    RECENT_LIMIT = 200       # 环形缓冲上限：只留最近 N 条明细，长跑进程不涨内存

    def __init__(self):
        self._lock = threading.Lock()
        self._total = TokenUsage()
        self._by_model: Dict[str, Dict[str, Any]] = {}
        self._recent: List[TokenUsage] = []
        self._listeners: List[Callable[[TokenUsage], None]] = []
        self._calls = 0

    def record(self, usage: TokenUsage) -> TokenUsage:
        """记一条用量，返回同一个对象（方便调用方链式取字段）。"""
        if usage.total_tokens <= 0:
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

        with self._lock:
            self._calls += 1
            self._total.prompt_tokens += usage.prompt_tokens
            self._total.completion_tokens += usage.completion_tokens
            self._total.total_tokens += usage.total_tokens

            slot = self._by_model.setdefault(
                usage.model or "unknown",
                {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                 "total_tokens": 0, "estimated_calls": 0},
            )
            slot["calls"] += 1
            slot["prompt_tokens"] += usage.prompt_tokens
            slot["completion_tokens"] += usage.completion_tokens
            slot["total_tokens"] += usage.total_tokens
            if usage.estimated:
                slot["estimated_calls"] += 1

            self._recent.append(usage)
            if len(self._recent) > self.RECENT_LIMIT:
                del self._recent[:-self.RECENT_LIMIT]

            listeners = list(self._listeners)

        for cb in listeners:
            try:
                cb(usage)
            except Exception:      # 接入方回调出错不能影响主链路
                pass
        return usage

    def on_usage(self, callback: Callable[[TokenUsage], None]) -> None:
        """注册用量回调（接入方据此落库 / 上报计费系统）。"""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def snapshot(self) -> Dict[str, Any]:
        """当前累计用量（含模型分组，以及「有几条是估算的」诚实标注）。"""
        with self._lock:
            return {
                "calls": self._calls,
                "prompt_tokens": self._total.prompt_tokens,
                "completion_tokens": self._total.completion_tokens,
                "total_tokens": self._total.total_tokens,
                "estimated_calls": sum(
                    s["estimated_calls"] for s in self._by_model.values()),
                "by_model": {m: dict(v) for m, v in self._by_model.items()},
            }

    def recent(self, n: int = 20) -> List[Dict[str, Any]]:
        """最近 n 条明细（倒序，最新在前）。"""
        n = max(1, int(n))
        with self._lock:
            items = self._recent[-n:] if self._recent else []
        return [u.to_dict() for u in reversed(items)]

    def reset(self) -> None:
        """清零（测试与按周期结转用）。"""
        with self._lock:
            self._total = TokenUsage()
            self._by_model = {}
            self._recent = []
            self._calls = 0
