# Security Policy / 安全策略

## Reporting a Vulnerability / 报告漏洞

If you discover a security vulnerability in SOMA, please **do not** file a public issue.

Email the report to the repository maintainer. Include:

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

We will respond within **7 days** with an acknowledgment and a timeline for a fix.

## Scope / 范围

| Area | In Scope |
|------|----------|
| API key leakage via logs/memory | Yes |
| LLM prompt injection in user input | Yes |
| Unsafe file access in dashboard | Yes |
| Dependency supply chain | Yes |

## Supported Versions / 支持的版本

| Version | Supported |
|---------|-----------|
| 0.3.0b1 | Yes |
| < 0.3.0 | No |

## Best Practices for Users / 用户最佳实践

1. Always set `SOMA_API_KEY` environment variable when exposing the dashboard to networks
2. Never commit `dash/llm_config.json` — it is gitignored by default
3. Review LLM provider API keys before deploying to shared environments
