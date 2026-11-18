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
        memory_provider: Optional[Callable[[str], List[Dict]]] = None,
    ):
        self._scene_store = scene_store
        self._profile_store = profile_store
        self._cfg = config
        self._scene_extractor = scene_extractor or SceneExtractor()
        self._profile_extractor = profile_extractor or ProfileExtractor()
        # ★ 2026-11-17: 记忆来源。以前 `capture_scenes()` 里硬编码 `return 0`
        #   （注释写着"实际提取逻辑在 capture_from_memories()"），而唯一自动
        #   调用链 `remember() → on_new_memory() → capture_scenes()` 从不到达
        #   提取 —— 所以「自动场景提取」自 v0.10.0 起就是个空壳。
        #   现在由外部注入取数回调：uid → [{"content": ..., "importance": ...}]
        self._memory_provider = memory_provider

        # 每用户状态
        self._new_count: Dict[str, int] = {}           # 新记忆计数
        self._warmup_threshold: Dict[str, int] = {}     # 当前 warmup 阈值
        self._last_capture_time: Dict[str, float] = {}  # 上次捕获时间
        self._last_memory_time: Dict[str, float] = {}   # 最后新记忆时间
        self._total_scenes_created: Dict[str, int] = {} # 累计创建场景数
        # ★ 2026-11-18: 失败可见性 —— 连续失败要能升级成 ERROR 并计数，
        #   否则 LLM key 失效时 L2 会静默归零（生产踩过）。
        self._consecutive_failures: Dict[str, int] = {}
        self._total_failures: Dict[str, int] = {}
        # ★ 2026-11-18: 最近一次捕获的明细，供 capture_scenes_detailed() 读取。
        #   调用方需要区分「提取到了但被去重」与「压根没提取」——
        #   只看 int 返回值分不出来（生产上因此误判过 L2 没跑起来）。
        self._last_detail: Dict[str, Dict] = {}
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
        # ★ 2026-11-24: 这里原来还有一段**进程内**的冷却检查
        #   （`_last_capture_time`）。它和 DB 租约的 cooldown 是两套状态 ——
        #   多 worker 下各记各的，而且会先于 DB 判定挡住调用，导致
        #   `_last_detail` 里看不到原因。统一交给 `try_begin_capture` 判断。

        # ★ 2026-11-17: 这里以前是 `return 0`，注释写着「实际提取逻辑在
        #   capture_from_memories()」—— 但没有任何调用方会走到那边：
        #   `remember() → on_new_memory() → capture_scenes()` 这条唯一的自动
        #   链路每次都在这里返回 0，所以自动场景提取从来没真正跑过。
        #
        #   现在通过注入的 `memory_provider` 取近期记忆，再交给
        #   `capture_from_memories()` 走完整提取流程。
        #   没有 provider（老调用方直接构造 CapturePipeline）时保持原行为，
        #   仍返回 0 —— 向后兼容，不改变既有语义。
        if self._memory_provider is None:
            self._last_detail[uid] = {
                "extracted": 0, "created": 0, "skipped": 0,
                "reason": "no_provider", "error": None,
            }
            return 0
        try:
            memories = self._memory_provider(uid)
        except Exception as exc:
            _log.warning("取近期记忆失败，跳过本次场景提取: %s", exc)
            self._last_detail[uid] = {
                "extracted": 0, "created": 0, "skipped": 0,
                "reason": "provider_error", "error": str(exc),
            }
            return 0
        if not memories:
            self._last_detail[uid] = {
                "extracted": 0, "created": 0, "skipped": 0,
                "reason": "no_memories", "error": None,
            }
            return 0
        # ★ 2026-11-24（下游生产实测，P1）：这里原来写死 `force=True`，
        #   注释是「间隔保护已在上面检查过」—— 但上面查的是**进程内**的
        #   `_last_capture_time`，而跨进程冷却在 DB 租约里。硬编码 force=True
        #   透传到 `try_begin_capture` 后会走 `(force=1 OR cooldown<=now)` 的
        #   短路分支，**把跨进程冷却整个绕过**。
        #
        #   实测：user=1 在 4 分钟内被 3 个 worker 轮流捕获 5 次（间隔 36~107 秒，
        #   而冷却应是 300 秒），产出语义重复的场景
        #   （「团队沟通成本系统改善」vs 「12至20人团队沟通成本系统改善」）。
        #
        #   修：透传调用方的 force —— 手动 `capture_scenes(force=True)` 仍跳过
        #   冷却；自动链路（on_new_memory 传 force=False）走完整跨进程冷却。
        return self.capture_from_memories(memories, user_id=uid, force=force)

    def capture_from_memories(
        self, memories: List[Dict], user_id: str = "", force: bool = False,
    ) -> int:
        """从记忆列表中提取场景。供外部（SOMA_Agent）在触发时调用。"""
        uid = user_id or ""
        now = time.time()

        # ★ 2026-11-24: 删掉进程内的 `_last_capture_time` 冷却检查 ——
        #   冷却的唯一真相源是下面的 DB 租约。两套状态各自为政时，进程内
        #   那套会先挡住调用，且不在 `_last_detail` 里留下原因。

        # ★ 2026-11-18: 跨进程互斥。多 worker 部署时每个进程都有一份
        #   CapturePipeline，进程内节流管不到彼此 —— 同一批记忆会被各抽一次。
        #   租约拿不到就直接跳过（不是失败，是「别人在做」）。
        lease_owner = self._scene_store.try_begin_capture(
            uid, force=force, min_interval=self._cfg.scene_min_interval,
        )
        if lease_owner is None:
            _log.debug("跳过场景提取：另一个进程正在捕获或仍在冷却期（user=%s）", uid)
            self._last_detail[uid] = {
                "extracted": 0, "created": 0, "skipped": 0,
                "reason": "locked", "error": None,
            }
            return 0

        try:
            return self._capture_locked(
                memories, uid, force=force, now=now,
            )
        finally:
            self._scene_store.end_capture(
                uid, lease_owner, cooldown=self._cfg.scene_min_interval,
            )

    def _capture_locked(
        self, memories: List[Dict], uid: str, *, force: bool, now: float,
    ) -> int:
        """拿到租约后的实际提取流程。"""
        # 获取已有场景标题去重
        existing_scenes = self._scene_store.get_scenes(user_id=uid, top_k=50)
        existing_titles = [s["title"] for s in existing_scenes]

        # 调用提取器
        try:
            extracted = self._scene_extractor.extract(memories, existing_titles)
        except Exception as exc:
            # ★ 2026-11-18: 失败可见性。生产上曾因 LLM key 失效导致**每一次**
            #   抽取都失败，但只有一行 WARNING，场景恒为 0 却没人发现
            #   （下游排查花了不少时间）。现在连续失败会升级成 ERROR 并计数。
            self._consecutive_failures[uid] = \
                self._consecutive_failures.get(uid, 0) + 1
            self._total_failures[uid] = self._total_failures.get(uid, 0) + 1
            n = self._consecutive_failures[uid]
            if n == 1:
                _log.warning("场景提取失败（LLM 调用异常，第 1 次）: %s", exc)
            elif n < 3:
                _log.warning("场景提取连续失败 %d 次: %s", n, exc)
            else:
                _log.error(
                    "场景提取已连续失败 %d 次（user=%s）—— L2 处于静默降级状态，"
                    "请检查 LLM 配置/额度。最近一次错误: %s", n, uid, exc,
                )
            self._last_detail[uid] = {
                "extracted": 0, "created": 0, "skipped": 0,
                "reason": "failed", "error": str(exc),
            }
            return 0
        # 成功一次就清零连续失败
        self._consecutive_failures[uid] = 0
        if not extracted:
            self._last_detail[uid] = {
                "extracted": 0, "created": 0, "skipped": 0,
                "reason": "empty_extract", "error": None,
            }
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

        # ★ 2026-11-18: 返回值口径要能区分「提取了但全被去重」和「压根没提取」。
        #   生产上踩过：remember() 已经自动捕获过 3 条，随后手动
        #   capture_scenes(force=True) 返回 0，而表里确实有 3 条 —— 调用方
        #   据此误判「L2 没跑起来」，排查了很久。真相是本次提取的标题全部
        #   已存在（add_scene 同用户同标题去重），所以新增 0 条。
        if extracted and created == 0:
            _log.info(
                "场景提取完成但无新增（user=%s）：提取 %d 条，标题全部已存在"
                "（去重）。当前累计 %d 条。",
                uid, len(extracted), after_count,
            )
        self._last_detail[uid] = {
            "extracted": len(extracted),
            "created": created,
            "skipped": max(0, len(extracted) - created),
            "reason": "ok" if created > 0 else "no_new",
            "error": None,
        }

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
            "捕获完成: user=%s, 场景=%d, 累计场景=%d, 库里共 %d 条"
            "（reason=%s, 提取 %d 条, 去重 %d 条）",
            uid, created, self._total_scenes_created.get(uid, 0), after_count,
            "ok" if created > 0 else "no_new",
            len(extracted), max(0, len(extracted) - created),
        )

        # 检查是否触发 Profile 更新
        #
        # ★ 2026-11-24（下游生产实测）：原来这里是
        #     total = self._total_scenes_created.get(uid, 0)   # 进程内内存
        #     if total > 0 and total % interval == 0:          # 必须正好整除
        #   实测场景增长 8 → 13 → 19 → 25，每次都跨过 10/20 → **一次都没触发过**，
        #   用户攒了 19 条场景，画像是 0。
        #
        #   现在：计数用库里的真实场景数（持久 + 跨进程），阈值存 capture_lease，
        #   「>= 阈值就触发并推进」，并用带条件的 UPDATE 保证多 worker 下只触发一次。
        total = self._scene_store.count(uid)
        if total > 0 and self._scene_store.try_advance_profile_marker(
            uid, total, self._cfg.profile_scene_interval,
        ):
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
            # ★ 2026-11-18: 失败可见性 —— 这两个数长期 >0 且 scene_count 不涨，
            #   说明 L2 在静默降级（LLM key 失效 / 额度耗尽）。
            "consecutive_failures": self._consecutive_failures.get(uid, 0),
            "total_failures": self._total_failures.get(uid, 0),
            "capture_lease": self._scene_store.capture_lease_state(uid),
            "last_detail": self._last_detail.get(uid),
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
