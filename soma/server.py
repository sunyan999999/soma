"""SOMA Standalone HTTP Server — v2.0.9

提供独立的 REST API 服务，外部项目无需 pip install 即可通过 HTTP 调用 SOMA。
启动: python -m soma.server 或 soma-server

环境变量:
  SOMA_DATA_DIR — 数据目录 (默认 ./soma_data)
  SOMA_LLM — LLM 模型 (默认 mock，设为 deepseek-chat 启用真实推理)
  SOMA_PORT — 服务端口 (默认 8766)
"""
import os, sys, json, time
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("fastapi/uvicorn not installed. Run: pip install fastapi uvicorn")
    sys.exit(1)

app = FastAPI(title="SOMA API Server", version="2.0.9")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_soma = None

def get_soma():
    global _soma
    if _soma is None:
        from soma import SOMA
        persist = os.environ.get("SOMA_DATA_DIR", "soma_data")
        llm = os.environ.get("SOMA_LLM", "mock")
        _soma = SOMA(persist_dir=persist, llm=llm, enable_zhongdao="auto")
    return _soma


class ProblemRequest(BaseModel):
    problem: str
    use_llm: str = "auto"


class MemoryRequest(BaseModel):
    content: str
    importance: float = 0.7
    domain: str = "general"


# ── Core endpoints ──

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.9"}


@app.post("/api/reason")
def api_reason(req: ProblemRequest):
    t0 = time.time()
    result = get_soma().reason(req.problem, use_llm=req.use_llm)
    result["elapsed_ms"] = round((time.time() - t0) * 1000, 1)
    return result


@app.post("/api/chat")
def api_chat(req: ProblemRequest):
    t0 = time.time()
    result = get_soma().chat(req.problem)
    result["elapsed_ms"] = round((time.time() - t0) * 1000, 1)
    return result


@app.post("/api/loop")
def api_loop(req: ProblemRequest):
    t0 = time.time()
    result = get_soma().loop(req.problem)
    result["elapsed_ms"] = round((time.time() - t0) * 1000, 1)
    return result


@app.get("/api/memory/search")
def api_memory_search(q: str = "", top_k: int = 5):
    return {"results": get_soma().query_memory(q, top_k=top_k)}


@app.post("/api/memory/save")
def api_memory_save(req: MemoryRequest):
    mid = get_soma().remember(req.content, context={"domain": req.domain}, importance=req.importance)
    return {"id": mid, "status": "saved"}


@app.get("/api/stats")
def api_stats():
    s = get_soma()
    return {"memory": s.memory.stats(), "weights": s.evolver.get_weights()}


def main():
    import uvicorn
    port = int(os.environ.get("SOMA_PORT", "8766"))
    print(f"SOMA Server v2.0.9 starting on http://localhost:{port}")
    uvicorn.run("soma.server:app", host="0.0.0.0", port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
