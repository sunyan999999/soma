"""SOMA API Server — FastAPI 后端，为 Vue 前端提供 REST 接口"""
import asyncio
import json as _json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from soma.config import SOMAConfig, load_config
from soma.agent import SOMA_Agent
from soma.analytics import AnalyticsStore
from dash.providers import get_provider_manager

app = FastAPI(title="SOMA API", version="0.3.3b2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Key 认证中间件 ──────────────────────────────────────────

_SOMA_API_KEY = os.environ.get("SOMA_API_KEY", "").strip()
_AUTH_ENABLED = bool(_SOMA_API_KEY)
_AUTH_WHITELIST = {"/api/health", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """验证 X-API-Key 请求头（若启用认证）"""
    path = request.url.path
    if _AUTH_ENABLED and path.startswith("/api/") and path not in _AUTH_WHITELIST:
        api_key = request.headers.get("X-API-Key", "")
        if api_key != _SOMA_API_KEY:
            return _json_response(
                {"error": "未授权：缺少或无效的 API Key", "detail": "请设置 X-API-Key 请求头"},
                status_code=401,
            )
    return await call_next(request)


def _json_response(content: dict, status_code: int = 200):
    from starlette.responses import JSONResponse
    return JSONResponse(content=content, status_code=status_code)

# ── 静态前端资源 ──────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIR / "assets"

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


# ── Mock 模式 ──────────────────────────────────────────────────

MOCK_MODE = os.environ.get("SOMA_MOCK", "1") == "1"


def _use_mock() -> bool:
    """判断是否使用 Mock 模式：Mock 开启且当前提供商无 API Key 时使用 Mock"""
    if not MOCK_MODE:
        return False
    pm = get_provider_manager()
    return not bool(pm.get_current().get("api_key", ""))

_DATA_DIR = Path(os.environ.get("SOMA_DATA_DIR", "dashboard_data"))
_analytics: Optional[AnalyticsStore] = None

def _get_analytics() -> AnalyticsStore:
    global _analytics
    if _analytics is None:
        _analytics = AnalyticsStore(_DATA_DIR)
    return _analytics


def mock_llm_response(foci, activated, problem):
    """生成模拟的智者回答"""
    law_names = [f["law_id"] for f in foci]
    memory_count = len(activated)

    sections = ["## 问题拆解\n"]
    for f in foci:
        sections.append(
            f"### 从「{f['law_id']}」出发（权重: {f['weight']:.2f}）\n"
            f"{f['dimension'][:200]}\n"
        )

    if activated:
        sections.append("## 相关记忆分析\n")
        for am in activated[:5]:
            snippet = am["content"][:150]
            sections.append(
                f"- **[{am['source']}]** (关联度: {am['activation_score']:.3f})\n"
                f"  {snippet}...\n"
            )

    sections.append("## 综合建议\n")
    sections.append(
        f"针对问题「{problem}」，综合运用 {', '.join(law_names[:4])} 进行分析。\n"
    )

    id_map = {
        "first_principles": "1. **回归根本**：从最基本的要素出发，追问问题的本质原因\n",
        "systems_thinking": "2. **系统视角**：将问题置于更大的系统中，识别相关要素和反馈回路\n",
        "contradiction_analysis": "3. **矛盾剖析**：识别表面问题下的深层矛盾\n",
        "pareto_principle": "4. **关键少数**：聚焦影响最大的少数因素\n",
    }
    for law_id in law_names[:4]:
        if law_id in id_map:
            sections.append(id_map[law_id])

    if memory_count > 0:
        sections.append(
            f"\n> 💡 本次分析激活了 **{memory_count}** 条相关记忆\n"
        )

    sections.append(
        "\n---\n"
        "> ⚡ **Mock 模式** — 在 Settings 中配置真实 LLM 后即可获得完整深度分析"
    )

    return "\n".join(sections)


# ── 全局状态 ──────────────────────────────────────────────────

_agent: Optional[SOMA_Agent] = None
_initialized_mock = False


def get_agent() -> SOMA_Agent:
    global _agent, _initialized_mock
    if _agent is None:
        from soma import _DEFAULT_FRAMEWORK
        framework = load_config(_DEFAULT_FRAMEWORK)
        config = SOMAConfig(
            framework=framework,
            episodic_persist_dir=_DATA_DIR,
            default_top_k=5,
            recall_threshold=0.01,
            use_vector_search=True,
        )
        _agent = SOMA_Agent(config)

        if MOCK_MODE and not _initialized_mock:
            _initialized_mock = True
            # 仅在记忆库为空时注入示例数据，避免重启重复
            if _agent.memory.stats()["episodic"] == 0:
                _agent.remember(
                    "第一性原理：回归事物最基本的要素，从底层逻辑出发推导。"
                    "商业中这意味着不被竞争对手干扰，关注客户最根本的需求。",
                    {"domain": "哲学", "type": "理论"}, importance=0.95,
                )
                _agent.remember(
                    "系统思维：增长停滞是产品、市场、团队、流程等多个要素"
                    "相互作用形成的负反馈回路，需要找到关键杠杆点。",
                    {"domain": "思维", "type": "方法论"}, importance=0.9,
                )
                _agent.remember(
                    "二八法则：80%的增长瓶颈来自20%的核心问题。",
                    {"domain": "管理", "type": "案例"}, importance=0.85,
                )
                _agent.remember(
                    "逆向思考案例：某SaaS产品不研究'如何增长'，而是研究'用户为何流失'，"
                    "发现流失主因后反向改进，6个月内实现增长突破。",
                    {"domain": "营销", "type": "案例"}, importance=0.85,
                )
                _agent.remember(
                    "矛盾分析：增长停滞的表面问题是获客不足，"
                    "深层矛盾是产品价值交付与用户期望之间的差距。",
                    {"domain": "分析", "type": "框架"}, importance=0.8,
                )
            if _agent.memory.stats()["semantic"] == 0:
                _agent.remember_semantic("增长", "依赖", "创新")
                _agent.remember_semantic("增长", "受阻于", "路径依赖")
                _agent.remember_semantic("停滞", "源于", "价值交付不足")
                _agent.remember_semantic("系统思维", "关联", "矛盾分析")

    return _agent


# ── LiteLLM 调用 ──────────────────────────────────────────────

# LiteLLM 已知的提供商前缀，有这些前缀时 LiteLLM 会走专用路由（忽略 api_base）
_KNOWN_PREFIXES = (
    "openai/", "anthropic/", "gemini/", "deepseek/", "cohere/",
    "huggingface/", "together_ai/", "replicate/", "bedrock/",
    "vertex_ai/", "azure/", "ollama/", "mistral/", "groq/",
)

def call_llm(prompt: str, provider: dict) -> str:
    """使用 LiteLLM 调用 LLM，含 exponential backoff 重试和自动纠错"""
    import time
    from litellm import completion

    model = provider["model"]
    api_key = provider["api_key"]
    base_url = provider["base_url"].strip() if provider.get("base_url") and provider["base_url"].strip() else None

    # 自动修正：有自定义 base_url 但模型名缺少 openai/ 前缀时，自动补全
    if base_url and not model.startswith(_KNOWN_PREFIXES):
        print(f"[SOMA] 自动补全模型前缀: {model} → openai/{model}")
        model = f"openai/{model}"

    # 自动修正 base_url：去掉末尾 /chat/completions 避免重复
    if base_url and model.startswith("openai/"):
        base_url = base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-len("/chat/completions")]
            print(f"[SOMA] 自动裁剪 base_url 尾部: .../chat/completions → {base_url}")

    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url

    last_error = None
    for attempt in range(3):
        try:
            print(f"[SOMA] 正在调用 {model} (attempt {attempt+1}/3)...")
            response = completion(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            last_error = str(e)
            err_type = type(e).__name__
            print(f"[SOMA] LLM 调用失败 [{err_type}] (attempt {attempt+1}/3): {last_error[:200]}")

            # 不可重试的错误：认证、速率限制
            non_retryable = any(kw in last_error.lower() for kw in [
                "invalid api key", "incorrect api key", "401", "403",
                "rate limit", "quota", "insufficient_quota",
            ])
            if non_retryable:
                print(f"[SOMA] 不可重试的错误，停止重试")
                break

            # 可恢复错误：自动纠错后重试
            if "temperature" in last_error.lower() and "temperature" in kwargs:
                del kwargs["temperature"]
                print(f"[SOMA] 移除 temperature 参数后重试...")
                continue
            if "SSL" in last_error or "certificate" in last_error.lower():
                kwargs["ssl_verify"] = False
                continue

            # 网络/超时错误：exponential backoff
            if attempt < 2:
                wait_sec = 2 ** attempt  # 1s, 2s
                print(f"[SOMA] exponential backoff: 等待 {wait_sec}s 后重试...")
                time.sleep(wait_sec)

    raise RuntimeError(f"LLM 调用失败: {last_error}")


# ── Request Models ────────────────────────────────────────────

class ChatRequest(BaseModel):
    problem: str


class MemoryAddRequest(BaseModel):
    content: str
    domain: str = "通用"
    type: str = "笔记"
    importance: float = Field(default=0.7, ge=0.0, le=1.0)


class SemanticAddRequest(BaseModel):
    subject: str
    predicate: str
    object: str


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=20, ge=1, le=100)


class WeightAdjustRequest(BaseModel):
    law_id: str
    weight: float = Field(ge=0.0, le=1.0)


class ProviderSwitchRequest(BaseModel):
    provider_id: str


class ProviderUpdateRequest(BaseModel):
    provider_id: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None


# ── Health ───────────────────────────────────────────────────

@app.get("/api/health")
def health():
    agent = get_agent()
    pm = get_provider_manager()
    return {
        "status": "ok",
        "version": app.version,
        "mock_mode": _use_mock(),
        "current_provider": pm.current_provider_id,
        "memory_stats": agent.memory.stats(),
    }


# ── Config / Provider ────────────────────────────────────────

@app.get("/api/config/llm")
def config_llm():
    """获取当前 LLM 配置"""
    pm = get_provider_manager()
    all_providers = pm.get_providers()

    # 检查哪些提供商有 API key
    for pid, p in all_providers["providers"].items():
        p["has_key"] = bool(pm._config["providers"][pid]["api_key"])

    return {
        "mock_mode": _use_mock(),
        "current_provider": pm.current_provider_id,
        "current_config": {
            "model": pm.get_current()["model"],
            "base_url": pm.get_current()["base_url"] or None,
            "has_key": bool(pm.get_current()["api_key"]),
        },
        "providers": all_providers["providers"],
    }


@app.post("/api/config/providers/switch")
def config_switch_provider(req: ProviderSwitchRequest):
    """切换当前使用的提供商"""
    pm = get_provider_manager()
    ok = pm.switch_provider(req.provider_id)
    if not ok:
        raise HTTPException(404, f"提供商 '{req.provider_id}' 不存在")
    return {
        "current_provider": req.provider_id,
        "provider": pm.get_providers()["providers"][req.provider_id],
    }


@app.post("/api/config/providers/update")
def config_update_provider(req: ProviderUpdateRequest):
    """更新提供商配置（API key / model / base_url）"""
    pm = get_provider_manager()
    ok = pm.update_provider(
        req.provider_id,
        api_key=req.api_key,
        model=req.model,
        base_url=req.base_url,
    )
    if not ok:
        raise HTTPException(404, f"提供商 '{req.provider_id}' 不存在")
    providers = pm.get_providers()
    return {
        "provider_id": req.provider_id,
        "provider": providers["providers"][req.provider_id],
        "current_provider": pm.current_provider_id,
    }


# ── Chat ─────────────────────────────────────────────────────

@app.post("/api/chat")
def chat(req: ChatRequest):
    t0 = time.time()
    agent = get_agent()

    # Step 1: 拆解
    foci = agent.decompose(req.problem)
    foci_data = [
        {
            "law_id": f.law_id,
            "dimension": f.dimension,
            "keywords": f.keywords[:8],
            "weight": f.weight,
            "rationale": f.rationale,
        }
        for f in foci
    ]

    # Step 2: 激活
    activated = agent.hub.activate(foci)
    memory_cards = [
        {
            "id": am.memory.id,
            "content": am.memory.content,
            "activation_score": round(am.activation_score, 4),
            "source": am.source,
            "importance": am.memory.importance,
            "access_count": am.memory.access_count,
            "context": am.memory.context,
        }
        for am in activated
    ]

    # Step 3: 应答 — Mock 或动态 Provider
    use_mock = _use_mock()
    provider_id = "mock"
    llm_error = None
    if use_mock:
        # mock 模式也构建 prompt 供仪表盘可视化
        agent._build_prompt(req.problem, foci, activated)
        answer = mock_llm_response(foci_data, memory_cards, req.problem)
    else:
        pm = get_provider_manager()
        provider = pm.get_current()
        provider_id = pm.current_provider_id
        agent._build_prompt(req.problem, foci, activated)
        try:
            answer = call_llm(agent._last_prompt, provider)
        except Exception as llm_err:
            llm_error = str(llm_err)[:300]
            print(f"[SOMA] LLM 调用失败 [{provider_id}]，回退到 Mock 模式: {llm_error}")
            answer = mock_llm_response(foci_data, memory_cards, req.problem)
            # 回退时标记为 mock 模式
            use_mock = True
            provider_id = "mock"
        else:
            for am in activated:
                if am.source == "episodic":
                    try:
                        agent.memory.episodic.increment_access(am.memory.id)
                    except Exception as db_err:
                        print(f"[SOMA] WARNING: 访问计数更新失败: {db_err}")

    # 写入当前 foci/activated 上下文以追踪进化统计
    agent.evolver.set_current_context(foci, activated)

    agent.reflect(f"api_{len(agent.evolver.get_log())}", "success")

    # 每 10 次成功会话自动触发一次进化
    session_count = len(agent.evolver.get_log())
    if session_count > 0 and session_count % 10 == 0:
        changes = agent.evolver.evolve()
        if changes:
            print(f"[SOMA] 自动进化完成: {len(changes)} 项变更")

    response_time = (time.time() - t0) * 1000
    response_data = {
        "problem": req.problem,
        "mock_mode": use_mock,
        "foci": foci_data,
        "activated_memories": memory_cards,
        "answer": answer,
        "prompt": getattr(agent, '_last_prompt', ''),
        "memory_stats": agent.memory.stats(),
        "weights": agent.evolver.get_weights(),
        "provider_used": provider_id,
        "llm_error": llm_error,
    }

    # 记录到 AnalyticsStore
    try:
        analytics = _get_analytics()
        analytics.record_session({
            "id": f"session_{int(t0)}",
            "problem": req.problem,
            "mock_mode": use_mock,
            "provider_used": provider_id,
            "response_time_ms": round(response_time, 1),
            "foci": foci_data,
            "activated_memories": memory_cards,
            "answer": answer,
            "memory_stats": agent.memory.stats(),
            "weights": agent.evolver.get_weights(),
        })
    except Exception:
        pass  # analytics 异常不阻塞主流程

    return response_data


# ── Chat (SSE 流式) ────────────────────────────────────────────

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式聊天 — 通过 Server-Sent Events 逐步返回各阶段结果"""
    async def event_generator() -> AsyncGenerator[str, None]:
        t0 = time.time()
        agent = get_agent()

        # Phase 1: 拆解
        foci = agent.decompose(req.problem)
        foci_data = [
            {
                "law_id": f.law_id,
                "dimension": f.dimension,
                "keywords": f.keywords[:8],
                "weight": f.weight,
                "rationale": f.rationale,
            }
            for f in foci
        ]
        yield _sse_event("decompose", {"foci": foci_data})
        await asyncio.sleep(0)

        # Phase 2: 激活记忆
        activated = agent.hub.activate(foci)
        memory_cards = [
            {
                "id": am.memory.id,
                "content": am.memory.content,
                "activation_score": round(am.activation_score, 4),
                "source": am.source,
                "importance": am.memory.importance,
            }
            for am in activated
        ]
        yield _sse_event("activate", {"memories": memory_cards, "count": len(memory_cards)})
        await asyncio.sleep(0)

        # Phase 3: LLM 应答 (mock 或真实)
        use_mock = _use_mock()
        provider_id = "mock" if use_mock else get_provider_manager().current_provider_id

        llm_error = None
        if use_mock:
            answer = mock_llm_response(foci_data, memory_cards, req.problem)
            for i in range(0, len(answer), 80):
                chunk = answer[i:i+80]
                yield _sse_event("delta", {"content": chunk})
                await asyncio.sleep(0.02)
        else:
            pm = get_provider_manager()
            provider = pm.get_current()
            prompt = agent._build_prompt(req.problem, foci, activated)
            provider_id = pm.current_provider_id
            try:
                # 流式 LLM，逐 token 产出 delta 事件
                async for token_chunk in _token_stream(prompt, provider):
                    yield token_chunk
                    await asyncio.sleep(0)
            except Exception as llm_err:
                # 回退到非流式
                try:
                    answer = call_llm(prompt, provider)
                    yield _sse_event("delta", {"content": answer})
                except Exception as fallback_err:
                    # 最终兜底：Mock 模式
                    llm_error = str(fallback_err)[:300]
                    print(f"[SOMA] SSE LLM 调用失败 [{provider_id}]，回退到 Mock 模式: {llm_error}")
                    answer = mock_llm_response(foci_data, memory_cards, req.problem)
                    use_mock = True
                    provider_id = "mock"
                    yield _sse_event("delta", {"content": answer})
                    yield _sse_event("llm_fallback", {"message": llm_error})
            else:
                for am in activated:
                    if am.source == "episodic":
                        try:
                            agent.memory.episodic.increment_access(am.memory.id)
                        except Exception as db_err:
                            print(f"[SOMA] WARNING: SSE 访问计数更新失败: {db_err}")

        # 进化上下文
        agent.evolver.set_current_context(foci, activated)
        agent.reflect(f"api_stream_{len(agent.evolver.get_log())}", "success")

        session_count = len(agent.evolver.get_log())
        if session_count > 0 and session_count % 10 == 0:
            changes = agent.evolver.evolve()
            if changes:
                yield _sse_event("evolve", {"changes": changes})

        # Phase 4: 完成
        response_time = (time.time() - t0) * 1000
        yield _sse_event("done", {
            "provider_used": provider_id,
            "mock_mode": use_mock,
            "response_time_ms": round(response_time, 1),
            "memory_stats": agent.memory.stats(),
            "weights": agent.evolver.get_weights(),
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event: str, data: dict) -> str:
    """格式化 SSE 事件"""
    payload = _json.dumps(data, ensure_ascii=False)
    # 每个事件一行 event: + 一行 data: + 空行
    return f"event: {event}\ndata: {payload}\n\n"


async def _token_stream(prompt: str, provider: dict) -> AsyncGenerator[str, None]:
    """流式调用 LLM，逐 token 产出 SSE delta 事件"""
    from litellm import acompletion

    model = provider["model"]
    api_key = provider["api_key"]
    base_url = provider.get("base_url", "").strip()

    _KNOWN_PREFIXES = (
        "openai/", "anthropic/", "gemini/", "deepseek/", "cohere/",
        "huggingface/", "together_ai/", "replicate/", "bedrock/",
        "vertex_ai/", "azure/", "ollama/", "mistral/", "groq/",
    )
    if base_url and not model.startswith(_KNOWN_PREFIXES):
        model = f"openai/{model}"
    if base_url and model.startswith("openai/"):
        base_url = base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-len("/chat/completions")]

    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "stream": True,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url

    response = await acompletion(**kwargs)
    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta.content:
            yield _sse_event("delta", {"content": delta.content})

@app.get("/api/memory/stats")
def memory_stats():
    return get_agent().memory.stats()


@app.post("/api/memory/search")
def memory_search(req: MemorySearchRequest):
    results = get_agent().query_memory(req.query, top_k=req.top_k)
    return {"query": req.query, "results": results, "count": len(results)}


@app.post("/api/memory/add")
def memory_add(req: MemoryAddRequest):
    mid = get_agent().remember(
        req.content,
        context={"domain": req.domain, "type": req.type},
        importance=req.importance,
    )
    return {"id": mid, "status": "saved"}


@app.post("/api/memory/semantic")
def memory_add_semantic(req: SemanticAddRequest):
    get_agent().remember_semantic(req.subject, req.predicate, req.object)
    return {"status": "saved"}


# ── Framework ────────────────────────────────────────────────

@app.get("/api/framework/weights")
def framework_weights():
    return get_agent().evolver.get_weights()


@app.post("/api/framework/adjust-weight")
def framework_adjust(req: WeightAdjustRequest):
    ok = get_agent().evolver.adjust_weight(req.law_id, req.weight)
    if not ok:
        raise HTTPException(404, f"规律 '{req.law_id}' 不存在")
    return {"law_id": req.law_id, "new_weight": req.weight}


@app.post("/api/framework/evolve")
def framework_evolve():
    changes = get_agent().evolver.evolve()
    weights = get_agent().evolver.get_weights()
    return {"changes": changes, "weights": weights}


@app.get("/api/framework/stats")
def framework_stats():
    return get_agent().evolver.get_stats()


@app.get("/api/framework/log")
def framework_log():
    log = get_agent().evolver.get_log()
    return {"entries": list(reversed(log[-50:])), "total": len(log)}


@app.delete("/api/framework/log")
def framework_clear_log():
    get_agent().evolver.clear_log()
    return {"status": "cleared"}


class DiscoverLawsRequest(BaseModel):
    llm_model: Optional[str] = None


class ApproveLawRequest(BaseModel):
    candidate: dict


@app.post("/api/framework/discover-laws")
def framework_discover_laws(req: Optional[DiscoverLawsRequest] = None):
    """从高关联记忆簇中自动发现新思维规律。

    返回候选规律 dict（供人工审核），或 None 表示当前无条件生成。
    建议每 50 次会话调用一次。
    """
    agent = get_agent()
    if req and req.llm_model:
        llm_model = req.llm_model
    else:
        pm = get_provider_manager()
        llm_model = None if _use_mock() else pm.get_current().get("model", None)

    candidate = agent.evolver.discover_laws(
        embedder=agent.embedder,
        llm_model=llm_model,
    )
    if candidate is None:
        return {"status": "no_discovery", "candidate": None}
    return {"status": "discovered", "candidate": candidate}


@app.post("/api/framework/approve-law")
def framework_approve_law(req: ApproveLawRequest):
    """审批通过一条候选规律，将其加入思维框架。"""
    agent = get_agent()
    ok = agent.evolver.approve_law(req.candidate, embedder=agent.embedder)
    if not ok:
        raise HTTPException(400, "审批失败：候选规律无效或嵌入器未就绪")
    return {"status": "approved", "law_id": req.candidate.get("id", "unknown")}


# ── Analytics ────────────────────────────────────────────────

@app.get("/api/analytics/summary")
def analytics_summary():
    """获取汇总统计"""
    return _get_analytics().get_summary()


@app.get("/api/analytics/sessions")
def analytics_sessions(
    limit: int = 50,
    offset: int = 0,
    provider: Optional[str] = None,
    mock_only: Optional[bool] = None,
):
    """分页查询会话列表"""
    return _get_analytics().get_sessions(
        limit=limit, offset=offset, provider=provider, mock_only=mock_only
    )


@app.get("/api/analytics/session/{session_id}")
def analytics_session(session_id: str):
    """获取单次会话完整数据"""
    data = _get_analytics().get_session(session_id)
    if data is None:
        raise HTTPException(404, f"会话 '{session_id}' 不存在")
    return data


@app.get("/api/analytics/compare")
def analytics_compare():
    """返回对比分析数据（供图表使用）"""
    return _get_analytics().get_comparison_data()


@app.delete("/api/analytics/sessions")
def analytics_clear(keep: int = 200):
    """清理旧会话"""
    removed = _get_analytics().delete_old_sessions(keep)
    return {"removed": removed, "remaining": _get_analytics().count()}


# ── Benchmarks ──────────────────────────────────────────────

@app.get("/api/benchmarks/latest")
def benchmarks_latest():
    """获取最近一次基准测试结果"""
    result = _get_analytics().get_latest_benchmark()
    if result is None:
        raise HTTPException(404, "暂无基准测试数据，请先运行 benchmark")
    return result


@app.get("/api/benchmarks/history")
def benchmarks_history(limit: int = 20):
    """获取基准测试历史记录"""
    return _get_analytics().get_benchmark_history(limit=limit)


@app.get("/api/benchmarks/compare")
def benchmarks_compare():
    """获取 SOMA + 竞品对比数据"""
    return _get_analytics().get_benchmark_compare()


@app.post("/api/benchmarks/run")
def benchmarks_run():
    """触发一次完整基准测试"""
    try:
        from soma.benchmarks import run_full_benchmark
        agent = get_agent()
        # 尝试加载消融实验数据
        ablation_path = _DATA_DIR / "ablation_results.json"
        ablation_data = None
        if ablation_path.exists():
            import json as _json
            with open(ablation_path, "r", encoding="utf-8") as f:
                ablation_data = _json.load(f)
        run = run_full_benchmark(agent, ablation_data)
        run_id = _get_analytics().record_benchmark(run)
        return {
            "run_id": run_id,
            "scores": run.scores,
            "memory": asdict(run.memory),
            "wisdom": asdict(run.wisdom),
            "evolution": asdict(run.evolution),
            "scalability": asdict(run.scalability),
        }
    except Exception as e:
        raise HTTPException(500, f"基准测试运行失败: {str(e)[:300]}")


# ── Test Reports ──────────────────────────────────────────────

_REPORTS_DIR = Path(__file__).parent.parent / "reports"


def _parse_report_frontmatter(text: str) -> dict:
    """解析 markdown 文件的 YAML frontmatter"""
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    try:
        import yaml
        return yaml.safe_load(text[3:end])
    except Exception:
        return {}


@app.get("/api/reports")
def list_reports():
    """列出所有测试报告"""
    reports = []
    if _REPORTS_DIR.exists():
        for f in sorted(_REPORTS_DIR.glob("*.md"), reverse=True):
            content = f.read_text(encoding="utf-8")
            meta = _parse_report_frontmatter(content)
            # 提取摘要：第一个 # 标题后的第一段
            summary = ""
            lines = content.split("\n")
            in_content = False
            for line in lines:
                if line.startswith("# ") and not in_content:
                    in_content = True
                    continue
                if in_content and line.startswith("> "):
                    summary = line[2:].strip()
                    break
            reports.append({
                "id": meta.get("id", f.stem),
                "filename": f.name,
                "date": meta.get("date", ""),
                "version": meta.get("version", ""),
                "title": meta.get("title", f.stem),
                "title_en": meta.get("title_en", ""),
                "models": meta.get("models", []),
                "summary": summary,
            })
    return {"reports": reports, "total": len(reports)}


@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    """获取单篇报告完整内容 (Markdown)"""
    if not _REPORTS_DIR.exists():
        raise HTTPException(404, "报告目录不存在")

    for f in _REPORTS_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        meta = _parse_report_frontmatter(content)
        if meta.get("id") == report_id:
            return {
                "id": report_id,
                "filename": f.name,
                "meta": meta,
                "content": content,
            }
    raise HTTPException(404, f"报告 '{report_id}' 不存在")


# ── SPA 路由回退 ──────────────────────────────────────────────

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """将所有非 API 路径回退到 Vue SPA 入口，注入 API Key 配置"""
    index_html = FRONTEND_DIR / "index.html"
    if index_html.exists():
        html = index_html.read_text(encoding="utf-8")
        # 注入 API Key（若启用认证），供前端自动配置
        if _AUTH_ENABLED:
            inject = f'<script>window.__SOMA_API_KEY__ = "{_SOMA_API_KEY}";</script>'
            html = html.replace("</head>", inject + "\n</head>")
        return HTMLResponse(html)
    raise HTTPException(404, "Frontend not built. Run `npm run build` in dash/frontend.")


# ── Entrypoint ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    pm = get_provider_manager()
    print(f"\n{'='*50}")
    print(f"  SOMA API Server v{app.version}")
    print(f"  Mock 模式: {'✅ 开启' if _use_mock() else '❌ 关闭（使用真实模型）'}")
    if not MOCK_MODE:
        p = pm.get_current()
        print(f"  当前模型: {p['name']} ({p['model']})")
        print(f"  API Base: {p['base_url'] or '默认'}")
        print(f"  API Key:  {'已配置' if p['api_key'] else '❌ 未配置'}")
    print(f"{'='*50}\n")
    uvicorn.run("dash.server:app", host="0.0.0.0", port=8765, reload=True)
