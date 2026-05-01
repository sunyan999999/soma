# Contributing to SOMA

Thank you for your interest in contributing. SOMA is an open-source project under Apache 2.0 license, and we welcome contributions of all kinds.

## Code of Conduct

Be respectful. Be constructive. Assume good intent.

## How to Contribute

### Report Bugs

Open a GitHub Issue with:
- SOMA version (`python -c "import soma; print(soma.__version__)"`)
- Python version (`python --version`)
- Minimal reproduction steps
- Expected vs actual behavior

### Suggest Features

Open a GitHub Issue with:
- Problem statement (what pain does this solve?)
- Proposed solution sketch
- Why it belongs in SOMA core vs an external plugin

### Submit Code

1. **Fork** the repository
2. **Create a branch**: `feature/your-feature` or `fix/your-bug`
3. **Write code** following the conventions below
4. **Add tests** covering your changes
5. **Run the full suite**: `pytest -v --cov=soma --cov-report=term`
6. **Run linting**: `ruff check soma/ tests/`
7. **Run type checks**: `mypy soma/ --ignore-missing-imports`
8. **Commit** using conventional commit format (see below)
9. **Open a Pull Request** against the `main` branch

## Development Setup

```bash
git clone https://github.com/soma-project/soma-core.git
cd soma-core
pip install -e ".[dev]"
```

## Code Conventions

### Style
- Follow PEP 8, enforced by Ruff
- Line length: 100 characters
- Use type hints for public APIs

### Tests
- Framework: pytest
- Coverage target: > 80% for new code
- Pattern: table-driven tests preferred
- Assertions: plain `assert` statements

### Docstrings
- Public modules, classes, and functions must have docstrings
- Use Google-style docstring format

### Commit Format

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

Examples:
- `feat(engine): add jieba Chinese tokenization`
- `fix(memory): resolve dedup race condition`
- `docs(api): add SOMA.respond examples`

## Project Structure

```
soma/       # Core library — strict API stability
dash/       # Dashboard + REST server — may change
tests/      # All tests
docs/       # Documentation
examples/   # Integration examples
scripts/    # Benchmarks and utilities
```

## Pull Request Process

1. PR description must include: what, why, how tested
2. CI must pass (ruff + mypy + pytest + build)
3. At least one maintainer review required
4. PRs that change public API must update docs and CHANGELOG.md

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

---

# 贡献指南

感谢你对 SOMA 的关注。SOMA 是 Apache 2.0 许可下的开源项目，欢迎各种形式的贡献。

## 行为准则

尊重他人。建设性讨论。假定善意。

## 贡献方式

### 报告 Bug

提交 GitHub Issue，包含：
- SOMA 版本
- Python 版本
- 最小复现步骤
- 预期行为 vs 实际行为

### 建议功能

提交 GitHub Issue，包含：
- 问题描述（解决什么痛点？）
- 方案草图
- 为什么应该放在 SOMA 核心而非外部插件

### 提交代码

1. **Fork** 仓库
2. **创建分支**: `feature/功能名` 或 `fix/问题名`
3. **编写代码**，遵循以下规范
4. **添加测试**覆盖你的改动
5. **运行完整套件**: `pytest -v --cov=soma --cov-report=term`
6. **运行代码检查**: `ruff check soma/ tests/`
7. **运行类型检查**: `mypy soma/ --ignore-missing-imports`
8. **提交**使用约定式提交格式
9. **发起 Pull Request** 目标分支 `main`

## 开发环境配置

```bash
git clone https://github.com/soma-project/soma-core.git
cd soma-core
pip install -e ".[dev]"
```

## 代码规范

### 风格
- 遵循 PEP 8，Ruff 强制执行
- 行长度: 100 字符
- 公开 API 使用类型标注

### 测试
- 框架: pytest
- 覆盖率目标: 新代码 > 80%
- 模式: 优先使用 table-driven tests

### 文档字符串
- 公开模块、类、函数必须有 docstring
- 使用 Google 风格 docstring 格式

### 提交格式

```
<type>(<scope>): <description>
```

类型: `feat`、`fix`、`docs`、`test`、`refactor`、`chore`

## PR 流程

1. PR 描述必须包含: 做了什么、为什么、如何测试
2. CI 必须通过 (ruff + mypy + pytest + build)
3. 至少一位维护者审核
4. 修改公开 API 的 PR 必须同步更新文档和 CHANGELOG.md

## 许可

贡献即表示你同意将贡献以 Apache License 2.0 许可发布。
