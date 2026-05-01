#!/usr/bin/env python3
"""使用 gh CLI 批量提交 Awesome List PR。"""
import subprocess
import json
import sys
import base64


def gh(cli_args, stdin_data=None):
    """Run 'gh api <cli_args>' and return parsed JSON or None."""
    cmd = ["gh", "api"]
    # Always add --input - when piping data via stdin
    if stdin_data is not None:
        cmd.extend(["--input", "-"])
    cmd.extend(cli_args)
    result = subprocess.run(cmd, capture_output=True, text=True, input=stdin_data)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        print(f"  gh api ERR [{result.returncode}]: {stderr[:250]}")
        return None
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()


def run(cmd_args):
    """Run shell command, return (ok, output)."""
    result = subprocess.run(cmd_args, capture_output=True, text=True, shell=True)
    return result.returncode == 0, result.stdout + result.stderr


def get_default_branch(owner, repo):
    data = gh(["repos/{}/{}".format(owner, repo), "--jq", ".default_branch"])
    return data if data else "main"


def get_readme(owner, repo):
    data = gh(["repos/{}/{}/readme".format(owner, repo)])
    if not data:
        return None, None
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]


def create_branch(owner, repo, branch, default_branch):
    """Create new branch from default branch. Deletes existing if any."""
    # Get base SHA
    ref = gh(["repos/{}/{}/git/ref/heads/{}".format(owner, repo, default_branch)])
    if not ref:
        print(f"    Cannot get ref for {default_branch}")
        return False
    base_sha = ref["object"]["sha"]

    # Delete existing branch
    gh(["--silent", "-X", "DELETE",
        "repos/{}/{}/git/refs/heads/{}".format(owner, repo, branch)])

    # Create branch
    body = json.dumps({"ref": "refs/heads/" + branch, "sha": base_sha})
    result = gh(["-X", "POST", "repos/{}/{}/git/refs".format(owner, repo)],
                stdin_data=body)
    return result is not None


def commit_file(owner, repo, branch, path, content, sha, message):
    """Put file to branch."""
    body = json.dumps({
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha,
        "branch": branch,
    })
    result = gh(["-X", "PUT", "repos/{}/{}/contents/{}".format(owner, repo, path)],
                stdin_data=body)
    return result is not None


def create_pr(target_owner, target_repo, head_full, title, body, base_branch):
    """Create pull request."""
    pr_body = json.dumps({
        "title": title,
        "body": body,
        "head": head_full,
        "base": base_branch,
    })
    result = gh(["--method", "POST",
                 "repos/{}/{}/pulls".format(target_owner, target_repo)],
                stdin_data=pr_body)
    return result


def insert_entry(content, entry, anchor_before=None, anchor_after=None):
    if anchor_before:
        idx = content.find(anchor_before)
        if idx == -1:
            print(f"    WARNING: anchor_before not found")
            return None
        return content[:idx] + entry + content[idx:]
    elif anchor_after:
        idx = content.find(anchor_after)
        if idx == -1:
            print(f"    WARNING: anchor_after not found")
            return None
        end = content.find("\n", idx)
        if end == -1:
            end = idx + len(anchor_after)
        return content[:end + 1] + entry + content[end + 1:]
    return None


SUBMISSIONS = [
    {
        "target": "e2b-dev/awesome-ai-agents",
        "branch": "add/soma-cognitive-architecture",
        "pr_title": "Add SOMA — framework-first cognitive architecture with self-evolving reasoning",
        "pr_body": """SOMA (Somatic Wisdom Architecture) is a lightweight cognitive framework that gives AI agents explicit reasoning capabilities — not just memory retrieval.

Key differentiators:
- **Wisdom framework**: 7 thinking laws (first-principles, systems thinking, etc.) for systematic problem decomposition
- **Bidirectional activation**: vector search + keyword RRF, both directions compete for true relevance
- **Meta-evolution**: auto-adjusts thinking law weights based on success/failure feedback
- **Zero infrastructure**: SQLite + ONNX, no vector DB or GPU required
- **Dashboard**: Vue 3 UI with real-time framework monitoring, benchmarks, and analytics
- **139 tests, ~97% coverage, Apache 2.0**""",
        "entry": """## [SOMA](https://github.com/sunyan999999/soma)
Framework-first cognitive architecture with self-evolving reasoning

<details>

### Category
Agent Memory & Reasoning

### Description
SOMA (Somatic Wisdom Architecture) gives AI agents structured reasoning via 7 thinking laws:
- **Wisdom laws**: first-principles, systems thinking, contradiction analysis, dialectical synthesis, problem-driven learning, ecological thinking, temporal depth
- **Bidirectional activation**: vector similarity + keyword RRF, both directions compete for true relevance
- **Meta-evolution**: auto-adjusts law weights every 10 sessions based on success/failure outcomes
- **Zero infrastructure**: SQLite + FAISS + ONNX embeddings — no vector DB or GPU required
- **Full toolkit**: Python SDK (`pip install soma-wisdom`) + REST API + Vue3 Dashboard + Docker deployment
- 139 tests, Apache 2.0

### Links
- [GitHub](https://github.com/sunyan999999/soma)
- [PyPI](https://pypi.org/project/soma-wisdom/)
- [Docs](https://sunyan999999.github.io/soma/)

</details>

""",
        "anchor_before": "## [Stackwise]",
        "default_branch": "main",
    },
    {
        "target": "Shubhamsaboo/awesome-llm-apps",
        "branch": "add/soma-wisdom-architecture",
        "pr_title": "Add SOMA — wisdom-based reasoning framework for LLM agents",
        "pr_body": """SOMA augments LLM agents with structured reasoning and self-improving memory.

How it works:
1. **Decompose**: Problem → 7 thinking dimensions (first-principles, contradiction analysis, etc.)
2. **Activate**: Bidirectional memory search (semantic + keyword RRF)
3. **Synthesize**: LLM answers with framework guidance + relevant memories
4. **Evolve**: Auto-adjusts weights every 10 sessions based on outcomes

One command start: `pip install soma-wisdom && python -m soma`""",
        "entry": "- [SOMA](https://github.com/sunyan999999/soma) — Wisdom architecture for LLM agents. Problem decomposition via thinking laws → bidirectional memory activation → synthesis + self-evolution. Python, REST API, dashboard included. `pip install soma-wisdom`.\n",
        "anchor_after": "### 🧑‍🏫 AI Agent Framework Crash Course",
        "default_branch": "main",
    },
    {
        "target": "vinta/awesome-python",
        "branch": "add/soma-wisdom-cognitive",
        "pr_title": "Add soma-wisdom — cognitive architecture for AI agents",
        "pr_body": """Add soma-wisdom to the AI and Agents section.

SOMA is a cognitive architecture for AI agents that combines thinking laws, bidirectional memory activation, and meta-evolution. Python SDK, REST API, Vue3 Dashboard. Apache 2.0, available on PyPI.""",
        "entry": "  - [soma-wisdom](https://github.com/sunyan999999/soma) - Cognitive architecture for AI agents with thinking laws, memory activation, and meta-evolution.\n",
        "anchor_after": "  - [pydantic-ai]",
        "default_branch": "master",
    },
    {
        "target": "ikaijua/Awesome-AITools",
        "branch": "add/soma-wisdom-cognitive",
        "pr_title": "Add SOMA — framework-first cognitive architecture for AI agents",
        "pr_body": """Add SOMA (体悟式智慧架构) to the AI Agent section.

SOMA is a framework-first cognitive architecture that gives AI agents structured reasoning via 7 thinking laws, bidirectional memory activation, and meta-evolution. Python SDK + REST API + Vue3 Dashboard. Apache 2.0.

- GitHub: https://github.com/sunyan999999/soma
- PyPI: https://pypi.org/project/soma-wisdom/
- Docs: https://sunyan999999.github.io/soma/""",
        "entry": "|SOMA (体悟式智慧架构)|Framework-first cognitive architecture for AI agents with 7 thinking laws and bidirectional memory activation. Self-evolving via meta-learning loop. Python SDK + REST API + Vue3 Dashboard. Apache 2.0.|[Github](https://github.com/sunyan999999/soma) ![GitHub Repo stars](https://img.shields.io/github/stars/sunyan999999/soma?style=social)|Free|\n",
        "anchor_before": "\n### Agent Skills",
        "default_branch": "main",
    },
]

FORK_OWNER = "sunyan999999"


def submit(sub):
    target_owner, target_repo = sub["target"].split("/")
    default_branch = sub["default_branch"]

    print(f"\n{'='*60}")
    print(f"目标: {sub['target']} (base: {default_branch})")

    # 1. Get fork README
    print("  1. 获取 fork README...")
    content, sha = get_readme(FORK_OWNER, target_repo)
    if not content:
        print("     FAILED")
        return None

    # 2. Insert entry
    new_content = insert_entry(content, sub["entry"],
                               sub.get("anchor_before"), sub.get("anchor_after"))
    if not new_content:
        return None
    print(f"  2. 条目已插入 ({len(content)} -> {len(new_content)} 字符)")

    # 3. Create branch
    print(f"  3. 创建分支 '{sub['branch']}'...")
    if not create_branch(FORK_OWNER, target_repo, sub["branch"], default_branch):
        print("     FAILED")
        return None

    # 4. Commit
    print("  4. 提交...")
    if not commit_file(FORK_OWNER, target_repo, sub["branch"], "README.md",
                       new_content, sha, sub["pr_title"]):
        print("     FAILED")
        return None

    # 5. Create PR
    print("  5. 创建 PR...")
    head = f"{FORK_OWNER}:{sub['branch']}"
    pr = create_pr(target_owner, target_repo, head, sub["pr_title"],
                   sub["pr_body"], default_branch)
    if pr and "html_url" in pr:
        print(f"  ✅ 成功: {pr['html_url']}")
        return pr["html_url"]
    else:
        print("  ❌ FAILED")
        return None


def main():
    # 仅运行指定的 submission（默认全部）
    targets = sys.argv[1:] if len(sys.argv) > 1 else None
    results = []
    for sub in SUBMISSIONS:
        if targets and sub["target"] not in targets:
            continue
        try:
            url = submit(sub)
            results.append((sub["target"], url))
        except Exception as e:
            print(f"  ⚠️ 异常: {e}")
            results.append((sub["target"], None))

    print(f"\n{'='*60}")
    print("结果:")
    for target, url in results:
        print(f"  {target}: {url or 'FAILED'}")


if __name__ == "__main__":
    main()
