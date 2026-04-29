"""双向激活调度器 — 门面模块（向后兼容）

实际实现已拆分至 soma.hub 子包：
  _retriever.py — 多路召回
  _scorer.py    — 相关性打分
  _ranker.py    — MMR 多样性重排
  _core.py      — ActivationHub 门面编排
"""

from soma.hub._core import ActivationHub

__all__ = ["ActivationHub"]
