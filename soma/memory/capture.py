"""
自动捕获管道 — 响应用户记忆写入事件，自动聚合形成场景块和用户画像。

借鉴 TencentDB-Agent-Memory 的四层管线设计，简化为两部分：
- L1→L2: 情节记忆 → 场景块（warmup递增 + idle超时 + interval保护）
- L2→L3: 场景块 → 用户画像（scene累计触发）

所有触发调度在 CapturePipeline 内完成，LLM 提取由外部注入的提取器完成。
"""

import logging
import time
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from soma.memory.scene import SceneStore
from soma.memory.profile import ProfileStore

_log = logging.getLogger("soma.memory.capture")


# ── 数据类 ──

class CaptureConfig:
    """捕获管道配置 — 可从 SOMAConfig 中构造"""
    def __init__(
        self,
        scene_warmup: int = 5,
        scene_min_interval: int = 300,
        scene_max_interval: int = 3600,
        scene_idle_timeout: int = 600,
        profile_scene_interval: int = 10,
        enable_warmup: bool = True,
    ):
        self.scene_warmup = scene_warmup
        self.scene_min_interval = scene_min_interval
        self.scene_max_interval = scene_max_interval
        self.scene_idle_timeout = scene_idle_timeout
        self.profile_scene_interval = profile_scene_interval
        self.enable_warmup = enable_warmup


# ── 提取器接口 ──

class SceneExtractor:
    """场景提取器 — 从多条情节记忆中提取场景块。
    默认使用 LLM（通过 SOMA_Agent._call_llm），也支持 Mock 用于测试。"""

    def __init__(self, llm_call: Optional[Callable[[str], str]] = None):
        self._llm_call = llm_call or self._default_extract

    def extract(
        self, memories: List[Dict], existing_scene_titles: List[str],
    ) -> List[Dict]:
        """从记忆中提取场景块列表。每条包含 {title, summary, tags, importance, evidence_ids}。"""
        if not memories:
            return []

        # 构造 LLM prompt
        existing_hint = ""
        if existing_scene_titles:
            existing_hint = (
                "\n已有场景（避免重复）:\n" +
                "\n".join(f"- {t}" for t in existing_scene_titles[:10]) +
                "\n"
            )

        memory_texts = []
        for i, m in enumerate(memories):
            content = m.get("content", str(m))
            memory_texts.append(f"{i + 1}. {content[:300]}")

        prompt = (
            "你是一个知识组织专家。从以下近期记忆条目中提取场景块。\n"
            "一个场景块代表一个主题领域或工作上下文。\n"
            + existing_hint +
            f"\n近期记忆条数: {len(memory_texts)}\n" +
            "\n".join(memory_texts) +
            "\n\n请严格输出 JSON 格式，不要有任何额外文字：\n"
            '{"scenes": [{"title": "场景标题(简洁)", "summary": "2-3句话概括", '
            '"tags": ["标签1", "标签2"], "importance": 0.7, '
            '"evidence_ids": [对应的记忆序号如"1","2"]}]}\n'
        )

        raw = self._llm_call(prompt)
        return self._parse_response(raw)

    @staticmethod
    def _default_extract(prompt: str) -> str:
        """无 LLM 时的默认提取 — 返回空场景列表"""
        return '{"scenes": []}'

    @staticmethod
    def _parse_response(raw: str) -> List[Dict]:
        """解析 LLM 响应的 JSON，带基本容错"""
        import json as _json
        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError:
            # 尝试提取 JSON 片段
            for start, end in [("{", "}"), ("[", "]")]:
                try:
                    si = raw.index(start)
                    ei = raw.rindex(end) + 1
                    data = _json.loads(raw[si:ei])
                    break
                except (ValueError, _json.JSONDecodeError):
                    continue
            else:
                return []

        if isinstance(data, list):
            scenes = data
        elif isinstance(data, dict):
            scenes = data.get("scenes", [])
        else:
            return []
        if not isinstance(scenes, list):
            return []

        result = []
        for s in scenes:
            if not isinstance(s, dict):
                continue
            title = str(s.get("title", "")).strip()
            if not title:
                continue
            result.append({
                "title": title[:200],
                "summary": str(s.get("summary", title))[:2000],
                "tags": [
                    str(t).strip() for t in s.get("tags", [])
                    if str(t).strip()
                ][:10],
                "importance": max(0.1, min(1.0, float(s.get("importance", 0.5)))),
                "evidence_ids": [
                    str(e).strip() for e in s.get("evidence_ids", [])
                    if str(e).strip()
                ],
            })
        return result


class ProfileExtractor:
    """画像提取器 — 从场景块中提取用户画像条目。"""

    def __init__(self, llm_call: Optional[Callable[[str], str]] = None):
        self._llm_call = llm_call or self._default_extract

    def extract(
        self, scenes: List[Dict], existing_entries: List[Dict],
    ) -> List[Dict]:
        """从场景中提取用户画像条目。每条 {trait_type, trait_key, trait_value, confidence}。"""
        if not scenes:
            return []

        existing_hint = ""
        if existing_entries:
            existing_hint = (
                "\n已有画像（避免重复，可更新）:\n" +
                "\n".join(
                    f"- [{e.get('trait_type', '?')}] {e.get('trait_key', '?')} = {e.get('trait_value', str(e)[:60])}"
                    for e in existing_entries[:15]
                ) + "\n"
            )

        scene_texts = []
        for i, s in enumerate(scenes):
            scene_texts.append(
                f"{i + 1}. [{s.get('title', '?')}] {s.get('summary', '')[:300]}"
            )

        prompt = (
            "你是一个用户画像分析专家。从以下场景块中提取用户特征。\n"
            "特征类型: preference(偏好), skill(技能), habit(习惯), knowledge_gap(知识缺口), goal(目标)\n"
            + existing_hint +
            f"\n场景块数量: {len(scene_texts)}\n" +
            "\n".join(scene_texts) +
            "\n\n请严格输出 JSON 格式，不要有任何额外文字：\n"
            '{"entries": [{"type": "preference|skill|habit|knowledge_gap|goal", '
            '"key": "特征名", "value": "特征值", "confidence": 0.8}]}\n'
        )

        raw = self._llm_call(prompt)
        return self._parse_response(raw)

    @staticmethod
    def _default_extract(prompt: str) -> str:
        return '{"entries": []}'

    @staticmethod
    def _parse_response(raw: str) -> List[Dict]:
        import json as _json
        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError:
            for start, end in [("{", "}"), ("[", "]")]:
                try:
                    si = raw.index(start)
                    ei = raw.rindex(end) + 1
                    data = _json.loads(raw[si:ei])
                    break
                except (ValueError, _json.JSONDecodeError):
                    continue
            else:
                return []

        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("entries", [])
        else:
            return []
        if not isinstance(entries, list):
            return []

        valid_types = {"preference", "skill", "habit", "knowledge_gap", "goal"}
        result = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            tt = str(e.get("type", "")).strip()
            if tt not in valid_types:
                continue
            result.append({
                "trait_type": tt,
                "trait_key": str(e.get("key", "")).strip()[:200],
                "trait_value": str(e.get("value", "")).strip()[:500],
                "confidence": max(0.1, min(1.0, float(e.get("confidence", 0.5)))),
            })
        return result


# ── 捕获管道 ──

class CapturePipeline:
    """自动捕获管道 — 响应用户记忆写入，自动级联提取场景和画像。

    调度策略:
    - warmup: 新用户首次阈值 1，每次触发后翻倍直到 scene_warmup
    - idle: 有新记忆后 idle_timeout 秒无后续则触发
    - min_interval: 两次捕获间的最小间隔（防止 LLM 过载）
    - max_interval: 即使无新记忆也在此时间后检查一次（保底）
    """

    def __init__(
        self,
        scene_store: SceneStore,
        profile_store: ProfileStore,
        config: CaptureConfig,
        scene_extractor: Optional[SceneExtractor] = None,
        profile_extractor: Optional[ProfileExtractor] = None,
    ):
        self._scene_store = scene_store
        self._profile_store = profile_store
        self._cfg = config
        self._scene_extractor = scene_extractor or SceneExtractor()
        self._profile_extractor = profile_extractor or ProfileExtractor()

        # 每用户状态
        self._new_count: Dict[str, int] = {}           # 新记忆计数
        self._warmup_threshold: Dict[str, int] = {}     # 当前 warmup 阈值
        self._last_capture_time: Dict[str, float] = {}  # 上次捕获时间
        self._last_memory_time: Dict[str, float] = {}   # 最后新记忆时间
        self._total_scenes_created: Dict[str, int] = {} # 累计创建场景数
        self._enabled = True

    # ── 公共 API ──

    def on_new_memory(self, user_id: str) -> int:
        """有新记忆写入时调用。返回本次创建的场景数（0=未触发）。"""
        if not self._enabled:
            return 0

        uid = user_id or ""
        now = time.time()

        # 初始化 warmup 阈值
        if uid not in self._warmup_threshold:
            self._warmup_threshold[uid] = 1 if self._cfg.enable_warmup else self._cfg.scene_warmup

        self._new_count[uid] = self._new_count.get(uid, 0) + 1
        self._last_memory_time[uid] = now

        threshold = self._warmup_threshold[uid]
        count = self._new_count[uid]

        # 检查间隔保护
        last_cap = self._last_capture_time.get(uid, 0)
        if count < threshold:
            # 检查 idle 超时（通过 idle 检查的独立触发路径）
            if now - last_cap < self._cfg.scene_min_interval:
                return 0
            idle_since_last = now - self._last_memory_time.get(uid, now)
            if idle_since_last < self._cfg.scene_idle_timeout:
                return 0

        # 触发捕获
        scenes_created = self.capture_scenes(uid, force=False)
        if scenes_created > 0:
            self._last_capture_time[uid] = now
            self._new_count[uid] = 0
            self._total_scenes_created[uid] = (
                self._total_scenes_created.get(uid, 0) + scenes_created
            )

            # 更新 warmup 阈值
            if self._cfg.enable_warmup and threshold < self._cfg.scene_warmup:
                self._warmup_threshold[uid] = min(
                    threshold * 2, self._cfg.scene_warmup,
                )
            elif not self._cfg.enable_warmup:
                self._warmup_threshold[uid] = self._cfg.scene_warmup

        return scenes_created

    def capture_scenes(self, user_id: str, force: bool = False) -> int:
        """手动或自动触发场景提取。force=True 跳过间隔限制。返回新增场景数。"""
        if not self._enabled:
            return 0
        uid = user_id or ""
        now = time.time()

        if not force:
            last_cap = self._last_capture_time.get(uid, 0)
            if now - last_cap < self._cfg.scene_min_interval:
                return 0

        # 收集近期记忆 — 这里记忆由 SceneExtractor 通过传入的列表提供
        # SceneExtractor 需要从外部注入记忆列表
        # 此处 SceneStore 只存储结果，不直接管理 episodic 数据
        return 0  # 实际提取逻辑在 capture_from_memories()

    def capture_from_memories(
        self, memories: List[Dict], user_id: str = "", force: bool = False,
    ) -> int:
        """从记忆列表中提取场景。供外部（SOMA_Agent）在触发时调用。"""
        uid = user_id or ""
        now = time.time()

        if not force:
            last_cap = self._last_capture_time.get(uid, 0)
            if now - last_cap < self._cfg.scene_min_interval:
                return 0

        # 获取已有场景标题去重
        existing_scenes = self._scene_store.get_scenes(user_id=uid, top_k=50)
        existing_titles = [s["title"] for s in existing_scenes]

        # 调用提取器
        try:
            extracted = self._scene_extractor.extract(memories, existing_titles)
        except Exception as exc:
            _log.warning("场景提取失败（LLM 调用异常）: %s", exc)
            return 0
        if not extracted:
            return 0

        created = 0
        before_count = self._scene_store.count(uid)
        for scene_data in extracted:
            try:
                self._scene_store.add_scene(
                    title=scene_data["title"],
                    summary=scene_data["summary"],
                    tags=scene_data.get("tags"),
                    evidence_ids=scene_data.get("evidence_ids"),
                    importance=scene_data.get("importance", 0.5),
                    user_id=uid,
                )
            except Exception as exc:
                _log.warning("场景创建失败: %s", exc)
        after_count = self._scene_store.count(uid)
        created = max(0, after_count - before_count)

        self._last_capture_time[uid] = now
        self._total_scenes_created[uid] = (
            self._total_scenes_created.get(uid, 0) + created
        )

        # 更新 warmup 阈值
        if created > 0 and uid in self._warmup_threshold:
            t = self._warmup_threshold[uid]
            if self._cfg.enable_warmup and t < self._cfg.scene_warmup:
                self._warmup_threshold[uid] = min(t * 2, self._cfg.scene_warmup)
            elif not self._cfg.enable_warmup:
                self._warmup_threshold[uid] = self._cfg.scene_warmup

        _log.info(
            "捕获完成: user=%s, 场景=%d, 累计场景=%d",
            uid, created, self._total_scenes_created.get(uid, 0),
        )

        # 检查是否触发 Profile 更新
        total = self._total_scenes_created.get(uid, 0)
        if total > 0 and total % self._cfg.profile_scene_interval == 0:
            self.update_profile(uid, force=force)

        return created

    def update_profile(self, user_id: str, force: bool = False) -> int:
        """触发用户画像更新。返回新增/更新的条目数。"""
        uid = user_id or ""

        recent_scenes = self._scene_store.get_scenes(user_id=uid, top_k=50)
        if not recent_scenes:
            return 0

        existing_entries = self._profile_store.get_entries(user_id=uid)

        try:
            extracted = self._profile_extractor.extract(recent_scenes, existing_entries)
        except Exception as exc:
            _log.warning("画像提取失败（LLM 调用异常）: %s", exc)
            return 0
        if not extracted:
            return 0

        updated = 0
        for entry_data in extracted:
            try:
                self._profile_store.upsert_entry(
                    trait_type=entry_data["trait_type"],
                    trait_key=entry_data["trait_key"],
                    trait_value=entry_data["trait_value"],
                    confidence=entry_data.get("confidence", 0.5),
                    user_id=uid,
                    source_scene_ids=[s["id"] for s in recent_scenes[:5]],
                )
                updated += 1
            except Exception as exc:
                _log.warning("画像条目更新失败: %s", exc)

        _log.info(
            "画像更新完成: user=%s, 条目=%d (新增/更新)", uid, updated,
        )
        return updated

    def check_idle(self, user_id: str = "") -> int:
        """检查空闲超时并触发捕获（由外部定时器定期调用）。返回场景数。"""
        uid = user_id or ""
        now = time.time()

        # 检查是否空闲超时
        last_memory = self._last_memory_time.get(uid, 0)
        if last_memory == 0:
            return 0
        if now - last_memory < self._cfg.scene_idle_timeout:
            return 0

        # 检查是否有新记忆待处理
        if self._new_count.get(uid, 0) == 0:
            return 0

        # 检查最小间隔
        last_cap = self._last_capture_time.get(uid, 0)
        if now - last_cap < self._cfg.scene_min_interval:
            return 0

        return self.capture_scenes(uid, force=True)

    def get_state(self, user_id: str = "") -> Dict:
        """获取当前管道状态（调试用）"""
        uid = user_id or ""
        return {
            "enabled": self._enabled,
            "new_count": self._new_count.get(uid, 0),
            "warmup_threshold": self._warmup_threshold.get(uid, self._cfg.scene_warmup),
            "last_capture_time": self._last_capture_time.get(uid, 0),
            "last_memory_time": self._last_memory_time.get(uid, 0),
            "total_scenes": self._total_scenes_created.get(uid, 0),
            "scene_count": self._scene_store.count(uid),
            "profile_count": self._profile_store.count(uid),
        }

    def disable(self):
        self._enabled = False

    def enable(self):
        self._enabled = True

    def close(self):
        self._enabled = False
        self._new_count.clear()
        self._warmup_threshold.clear()
        self._last_capture_time.clear()
        self._last_memory_time.clear()
