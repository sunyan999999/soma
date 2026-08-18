# -*- coding: utf-8 -*-
"""SourceTrust 来源可信度测试 — v2.0.9"""
from soma.source_trust import SourceTrust, SourceTrustConfig


def test_whitelist_high_trust():
    st = SourceTrust()
    score, verdict = st.rate("https://github.com/sunyan999999/soma")
    assert score >= 0.9
    assert verdict == "high"


def test_whitelist_subdomain_match():
    st = SourceTrust()
    # 子域匹配（www.wikipedia.org 或 zh.wikipedia.org → wikipedia.org）
    score, verdict = st.rate("https://zh.wikipedia.org/wiki/SOMA")
    assert verdict == "high"
    assert score >= 0.9


def test_blacklist_rejected():
    st = SourceTrust()
    score, verdict = st.rate("https://spam-site.com/click-here")
    assert score == 0.0
    assert verdict == "rejected"
    assert not st.is_trustworthy("https://spam-site.com/x")


def test_unknown_default():
    st = SourceTrust()
    score, verdict = st.rate("https://random-blog.xyz/article")
    assert score == 0.5
    assert verdict == "default"


def test_no_domain_rejected():
    st = SourceTrust()
    score, verdict = st.rate("not a url")
    # urlparse 无协议时 path 被当域名，unknown → default 或 rejected
    assert verdict in ("default", "rejected")


def test_custom_config():
    cfg = SourceTrustConfig(
        whitelist={"trusted.example.com": 0.95},
        blacklist={"bad.example.com"},
        default_score=0.4,
    )
    st = SourceTrust(cfg)
    assert st.rate("https://trusted.example.com/x")[1] == "high"
    assert st.rate("https://bad.example.com/x")[1] == "rejected"
    assert st.rate("https://other.example.com/x")[0] == 0.4


def test_www_prefix_stripped():
    st = SourceTrust()
    # www.github.com 应匹配 github.com 白名单
    score, verdict = st.rate("https://www.github.com/soma")
    assert verdict == "high"
    assert score >= 0.9
