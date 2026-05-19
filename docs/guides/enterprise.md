# Enterprise Deployment Guide / 企业部署指南

This guide covers production deployment of SOMA in enterprise environments with RBAC, audit logging, SSO integration, and private deployment patterns.

---

## 1. RBAC (Role-Based Access Control)

SOMA ships with a lightweight RBAC manager since v1.0.1.

### Roles & Permissions

| Role | read | write | delete | manage_users | manage_roles |
|------|:----:|:-----:|:------:|:------------:|:------------:|
| admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| writer | ✅ | ✅ | ❌ | ❌ | ❌ |
| reader | ✅ | ❌ | ❌ | ❌ | ❌ |

### Namespace Isolation

Each user is scoped to one or more namespaces. A memory stored in `project_alpha` is invisible to users without access to `project_alpha`.

```python
from soma.rbac import RBACManager

rbac = RBACManager()

# Create users with namespace scoping
rbac.create_user("alice", roles=["admin"], namespaces=["default", "project_alpha", "project_beta"])
rbac.create_user("bob", roles=["writer"], namespaces=["project_alpha"])
rbac.create_user("carol", roles=["reader"], namespaces=["project_alpha"])

# Permission checks before SOMA operations
def safe_remember(soma, rbac_manager, user_id, namespace, content, importance=0.5):
    if not rbac_manager.can_write(user_id, namespace):
        raise PermissionError(f"{user_id} cannot write to {namespace}")
    return soma.remember(content, context={"namespace": namespace}, importance=importance)

def safe_query(soma, rbac_manager, user_id, namespace, query, top_k=5):
    if not rbac_manager.can_read(user_id, namespace):
        raise PermissionError(f"{user_id} cannot read from {namespace}")
    return soma.query_memory(query, top_k=top_k)
```

### Persist RBAC State

```python
import json

# Save
with open("rbac_state.json", "w") as f:
    json.dump(rbac.to_dict(), f, indent=2)

# Restore
with open("rbac_state.json", "r") as f:
    rbac = RBACManager.from_dict(json.load(f))
```

---

## 2. Audit Logging

All memory CRUD operations can be tracked via the `AuditLogger`.

```python
from soma.audit import AuditLogger
from pathlib import Path

audit = AuditLogger(persist_dir=Path("soma_data"))

# Log every operation
def audited_remember(soma, audit_logger, user_id, content, **kwargs):
    mem_id = soma.remember(content, **kwargs)
    audit_logger.log("memory_create", user_id=user_id, details={
        "memory_id": mem_id,
        "content_preview": content[:200],
    })
    return mem_id

# Query audit trail
records = audit.query(
    user_id="alice",
    event_type="memory_delete",
    since=1700000000.0,  # Unix timestamp
    limit=100,
)

# Audit statistics
stats = audit.stats()
# {"total_events": 1523, "by_type": {"memory_create": 800, ...}, "by_user": {"alice": 500, ...}}
```

### Audit Event Types

| Event | Description |
|-------|-------------|
| `memory_create` | New episodic memory stored |
| `memory_read` | Memory retrieved via query |
| `memory_delete` | Memory explicitly deleted |
| `semantic_create` | New knowledge graph triple |
| `scene_extract` | L2 scene block extracted |
| `profile_update` | L3 user profile updated |
| `agent_register` | New expert agent registered |
| `config_change` | Framework configuration modified |
| `evolution_trigger` | Weight evolution executed |

### SOC2 / ISO27001 Compliance Notes

- **Immutability**: Audit records are append-only. The `audit_log` table has no UPDATE or DELETE in normal operation.
- **Retention**: Implement a retention policy via scheduled cleanup of records older than your required window.
- **Export**: Use `audit.query()` to export to your SIEM/Splunk/ELK pipeline.
- **PII**: The `details` field should not contain raw user input without sanitization. Content previews should be truncated.

---

## 3. SSO Integration Patterns

SOMA itself does not ship with an identity provider. Instead, integrate with your existing SSO via the `user_id` parameter throughout SOMA's API.

### Pattern: JWT Middleware (FastAPI Example)

```python
from fastapi import FastAPI, Depends, HTTPException
import jwt

app = FastAPI()

def get_current_user(authorization: str = Header(...)) -> str:
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]  # user_id
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401)

@app.post("/api/chat")
def chat(problem: str, user: str = Depends(get_current_user)):
    # SOMA operations scoped to JWT-authenticated user
    answer = soma.respond(problem, user_id=user)
    audit.log("memory_read", user_id=user, details={"problem": problem[:100]})
    return {"answer": answer}
```

### Supported SSO Providers

Any OIDC-compatible provider works by extracting `sub` as `user_id`:

- **Auth0**: Use `sub` claim
- **Okta**: Use `sub` or `preferred_username` claim
- **Keycloak**: Use `sub` claim
- **Azure AD**: Use `oid` or `sub` claim
- **AWS Cognito**: Use `sub` claim

---

## 4. Private Deployment

### Air-Gapped / Offline Deployment

SOMA runs entirely locally with zero external dependencies at runtime (ONNX + SQLite + FAISS, all local).

```bash
# 1. Download wheel on a connected machine
pip download soma-wisdom -d ./offline-packages/

# 2. Transfer to air-gapped machine
scp -r ./offline-packages/ airgap-server:/tmp/

# 3. Install offline
pip install --no-index --find-links /tmp/offline-packages/ soma-wisdom

# 4. Set local LLM (no external API calls)
export OLLAMA_HOST=localhost:11434
python -c "from soma import SOMA; s = SOMA(llm='ollama/llama3'); print(s.respond('hello'))"
```

### Resource Planning

| Scale | Memories | SQLite Size | FAISS Index | RAM | Recommended Hardware |
|-------|----------|-------------|-------------|-----|---------------------|
| Small | <10K | ~50MB | ~20MB | 512MB | 2 vCPU, any |
| Medium | 10K-100K | ~500MB | ~200MB | 2GB | 4 vCPU, SSD |
| Large | 100K-1M | ~5GB | ~2GB | 8GB | 8 vCPU, NVMe |

### Docker Deployment

```dockerfile
FROM python:3.11-slim

RUN pip install soma-wisdom

# Pre-download ONNX model
RUN python -c "from soma.embedder import SOMAEmbedder; from soma.config import SOMAConfig; \
    SOMAEmbedder(SOMAConfig())"

ENV SOMA_DATA_DIR=/data
VOLUME /data

EXPOSE 8765
CMD ["python", "dash/server.py"]
```

```bash
docker build -t soma-server .
docker run -v ./soma_data:/data -p 8765:8765 soma-server
```

---

## 5. SOC2 Self-Assessment Checklist

| Trust Service Criteria | SOMA Status | Notes |
|------------------------|-------------|-------|
| **Security** | ✅ | API keys via env vars; data isolation via persist_dir |
| **Availability** | ✅ | SQLite WAL mode; FAISS fallback to exact search |
| **Processing Integrity** | ✅ | Immutable audit log; content hashing for dedup |
| **Confidentiality** | ✅ | Namespace isolation; RBAC read/write boundaries |
| **Privacy** | ✅ | Surgical deletion by memory_id or user_id; audit trail |

**Key residual risks to address for full compliance:**

1. **Encryption at rest**: SQLite files are not encrypted. Use disk-level encryption (LUKS, BitLocker) or application-level encryption before storing sensitive data.
2. **Network encryption**: The REST API (dash/server.py) runs over HTTP by default. Use a reverse proxy (nginx, Caddy) with TLS in production.
3. **Key rotation**: API keys stored in env vars require manual rotation. Implement a secrets manager (Vault, AWS Secrets Manager) for automated rotation.
4. **Penetration testing**: Third-party pentest is recommended before handling PII/PHI in production.

---

## 6. Monitoring & Alerting

### Prometheus Metrics (via dash/server.py)

The built-in server exposes analytics endpoints that can be scraped:

```bash
curl http://localhost:8765/api/analytics/summary
# {"total_sessions": 234, "total_memories": 1050, "avg_latency_ms": 209}
```

### Health Check

```bash
curl http://localhost:8765/api/health
# {"status": "ok", "version": "1.0.0"}
```

Integrate with your existing monitoring stack (Prometheus + Grafana, Datadog, New Relic) via these endpoints.

---

# 企业部署指南

## RBAC 角色权限
- **admin**: 全部 namespace 读写 + 用户管理
- **writer**: 指定 namespace 读写
- **reader**: 指定 namespace 只读

## 审计日志
所有记忆 CRUD 操作通过 AuditLogger 记录到 SQLite。append-only 不可变存储。支持按用户/操作类型/时间范围检索。

## SSO 集成
通过 JWT `sub` 声明提取 `user_id`，与 Auth0/Okta/Keycloak/Azure AD/Cognito 等兼容。

## 私有部署
支持完全离线部署（ONNX + SQLite + FAISS 全本地）。单机支持 10K~1M 记忆。提供 Docker 部署方案。

## SOC2 自查
五项信任服务标准均可满足。关键残留风险：静态加密、网络加密、密钥轮换、渗透测试。
