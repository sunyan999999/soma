"""来源可信度分级 — 外部知识的来源信誉评估

外部知识（尤其 URL 抓取）的准确度保障第一步是评估来源可信度：
- 白名单域名（官方/权威站点）→ 高可信
- 黑名单域名（广告/恶意/已知低质）→ 拒绝
- 未知域名 → 默认信誉分（可配置）

供 KnowledgeGate 层0过滤与 URLSource 来源校验复用。纯本地，零 LLM 调用。
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple
from urllib.parse import urlparse

# 默认配置：常见权威域名示例（用户可按需覆盖）
DEFAULT_WHITELIST = {
    "github.com": 0.95,
    "wikipedia.org": 0.90,
    "gov.cn": 0.90,
    "ac.cn": 0.90,
    "who.int": 0.90,
    "arxiv.org": 0.90,
}
DEFAULT_BLACKLIST = {
    "example.com",
    "spam-site.com",
}
DEFAULT_UNKNOWN_SCORE = 0.5


@dataclass
class SourceTrustConfig:
    """来源可信度配置"""

    whitelist: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WHITELIST))
    blacklist: set = field(default_factory=lambda: set(DEFAULT_BLACKLIST))
    default_score: float = DEFAULT_UNKNOWN_SCORE
    # 黑名单直接拒绝的阈值
    reject_below: float = 0.1


class SourceTrust:
    """来源可信度评估器 — 解析 URL 域名，查表打分"""

    def __init__(self, config: SourceTrustConfig = None):
        self._config = config or SourceTrustConfig()

    def rate(self, url: str) -> Tuple[float, str]:
        """评估 URL 来源可信度。

        Returns:
            (score, verdict): score 0-1, verdict in {high, default, low, rejected}
        """
        domain = self._extract_domain(url)
        if not domain:
            return 0.0, "rejected"  # 无有效域名视为不可信

        # 黑名单优先
        if domain in self._config.blacklist:
            return 0.0, "rejected"

        # 白名单查表（支持子域名匹配：xxx.github.io → github 域）
        score = self._config.default_score
        for trusted, s in self._config.whitelist.items():
            if domain == trusted or domain.endswith("." + trusted):
                score = s
                break

        if score >= 0.8:
            return score, "high"
        if score <= self._config.reject_below:
            return score, "rejected"
        return score, "default"

    @staticmethod
    def _extract_domain(url: str) -> str:
        """从 URL 提取主域名（去掉 www 前缀）。"""
        try:
            parsed = urlparse(url)
            host = parsed.netloc or parsed.path
            host = host.lower()
        except Exception:
            return ""
        # 去掉端口和 www 前缀
        if ":" in host:
            host = host.split(":")[0]
        host = host.lstrip("www.")
        return host

    def is_trustworthy(self, url: str) -> bool:
        """快捷判断：是否达到可信水平（非 rejected）。"""
        _, verdict = self.rate(url)
        return verdict != "rejected"
