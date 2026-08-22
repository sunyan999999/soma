# Security Policy / 安全策略

## Supported Versions / 支持的版本

| Version | Supported          |
|---------|--------------------|
| 2.0.x   | :white_check_mark: |
| 1.1.x   | :white_check_mark: |
| < 1.1   | :x:                |

## Reporting a Vulnerability / 报告漏洞

请勿公开披露安全漏洞。请通过 GitHub Security Advisory 私下报告：
https://github.com/sunyan999999/soma/security/advisories/new

或发送邮件至项目维护者。我们将在 48 小时内响应。

## Security Design Principles / 安全设计原则

1. **零硬编码密钥** — 所有 API Key/Token 从环境变量读取，不在代码中存储
2. **最小权限** — 各组件仅访问所需的最小数据范围
3. **SQL 注入防护** — 全部使用参数化查询，无字符串拼接 SQL
4. **本地优先** — SOMA 默认纯本地运行，不上传数据到外部服务
5. **数据隔离** — user_id/session_id/agent_id 三列全链路透传

## Security Features / 安全特性

| 特性 | 说明 |
|------|------|
| API Key 认证 | SOMA Server 支持 X-API-Key 头部认证 |
| 数据隔离 | 用户/会话/Agent 三级数据隔离 |
| RBAC | 基于角色的访问控制（`soma.rbac`） |
| 审计日志 | SQLite 持久化审计，记录所有 CRUD 操作 |
| CORS | Server 模式可配置允许的源 |
| 输入验证 | 所有外部输入经过 Pydantic 模型校验 |

## Dependency Scanning / 依赖扫描

```bash
pip-audit
# 或
python -m pip install --upgrade pip-audit && pip-audit
```

## Known Limitations / 已知限制

- SOMA Server 默认无 HTTPS（建议反向代理添加）
- MCP Server 通过 stdio 通信，无网络暴露
- fastembed ONNX 推理依赖 HuggingFace 模型下载（首次使用需网络）

## Security Audit History / 安全审计历史

| 日期 | 审计方 | 范围 | 结果 |
|------|--------|------|------|
| 2026-07-08 | Qoder CN | Claude Code 环境全量审计 | P0 已修复，P1/P2 已完成 |
| 2026-07-26 | Claude Code | SOMA v2.0.6-dev 代码安全扫描 | 零漏洞，零硬编码密钥 |
| 2026-08-16 | Claude Code | SOMA v2.0.7 安全审计 | 修复 --project 路径穿越漏洞（正则白名单）+ importance 越界钳制 |
| 2026-08-17 | Claude Code | SOMA v2.0.8 安全审计 | 依赖锁定（litellm/fastembed）防升级漂移 + 激活异常不再静默吞掉 |
| 2026-08-18 | Claude Code | SOMA v2.0.9 安全审计 | 外部知识来源可信度过滤（黑名单域名拒绝）+ 内容质量检测防垃圾注入 |
| 2026-08-22 | Claude Code | SOMA v2.0.11 安全审计 | 向量索引一致性修复（faiss 存储异常不再静默吞掉）+ 日志区分 embed/索引写入失败 |
| 2026-08-19 | Claude Code | SOMA v2.0.10 安全审计 | 多模态记忆输入校验（图片路径/表格解析）+ 知识门控 API 参数校验 |
