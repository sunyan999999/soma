#!/usr/bin/env python3
"""SOMA 版本一致性检查 — 在 git push 前自动运行。

检查项:
1. pyproject.toml 版本号 ↔ git tag v{version} 一致性
2. 关键目录是否被当前版本标签触及（避免 GitHub 文件列表显示旧版本号）
3. GitHub Release v{version} 是否存在

用法:
  python scripts/version_guard.py        # 检查模式（pre-push hook 用）
  python scripts/version_guard.py --fix  # 自动修复缺失的标签和 Release
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# GitHub 文件列表旁会显示最后提交消息，这些目录需要保持新鲜
KEY_DIRS = [".github", "benchmark_data", "soma", "dash", "docs", "tests"]


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kwargs)


def read_version() -> str:
    """从 pyproject.toml 读取当前版本号。"""
    content = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not m:
        print("✗ 无法从 pyproject.toml 解析版本号")
        sys.exit(1)
    return m.group(1)


def tag_exists(version: str) -> bool:
    """检查 git tag v{version} 是否存在于本地。"""
    result = run(["git", "tag", "-l", f"v{version}"])
    return result.stdout.strip() == f"v{version}"


def get_latest_version_tag() -> str | None:
    """获取最新的版本标签名称（不包括非版本标签）。"""
    result = run(["git", "tag", "--sort=-version:refname"])
    for line in result.stdout.strip().split("\n"):
        if re.match(r"^v\d+\.\d+\.\d+", line):
            return line
    return None


def release_exists(version: str) -> bool:
    """检查 GitHub Release 是否存在。"""
    result = run(["gh", "release", "view", f"v{version}"])
    return result.returncode == 0


def check_dir_freshness(version_tag: str, version: str) -> list[str]:
    """检查关键目录的最后提交是否 >= 版本标签。返回陈旧的目录列表。"""
    stale = []
    for d in KEY_DIRS:
        if not (ROOT / d).exists():
            continue
        # 取该目录的最后一次提交
        r = run(["git", "log", "-1", "--format=%H", "--", d])
        last_commit = r.stdout.strip()
        if not last_commit:
            continue
        # 判断目录的最后提交是否已包含在版本标签中
        # is-ancestor(A, B): A 是 B 的祖先？→ 目录提交是否在标签之前
        r2 = run([
            "git", "merge-base", "--is-ancestor",
            last_commit, version_tag
        ])
        if r2.returncode != 0:
            # 目录最后提交在标签之后 → 该目录在版本发布后又改了
            # 这是正常情况，不报 stale
            pass
        else:
            # 目录最后提交在标签之前（含在发布中）
            # 检查提交消息中是否含旧版本号
            r3 = run(["git", "log", "-1", "--format=%s", "--", d])
            msg = r3.stdout.strip()
            old_ver = re.findall(r'v(\d+\.\d+\.\d+)', msg)
            if old_ver:
                displayed = old_ver[0]
                if displayed != version:
                    stale.append(d)
    return stale


def check_push_target() -> str | None:
    """读取 pre-push hook 传入的推送目标，检查是否推送到 main。"""
    # pre-push hook 通过 stdin 传入 <local ref> <local sha> <remote ref> <remote sha>
    # 这里只关心远程引用名
    lines = sys.stdin.read().strip().split("\n")
    for line in lines:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 3 and "main" in parts[2]:
            return parts[2]
    return None


def main():
    fix_mode = "--fix" in sys.argv

    version = read_version()
    tag = f"v{version}"
    errors = []

    # ── 检查1: 标签存在性 ──
    if tag_exists(version):
        print(f"✓ 版本 {version} → 标签 {tag} 存在")
    else:
        print(f"✗ 版本 {version} → 标签 {tag} 不存在")
        errors.append("tag")

    # ── 检查2: 目录新鲜度 ──
    if errors:
        # 标签不存在则跳过新鲜度检查（没基准点）
        print("  ⚠ 跳过目录新鲜度检查（标签缺失）")
    else:
        stale = check_dir_freshness(tag, version)
        if stale:
            print(f"⚠ 以下目录的最后提交早于 {tag}，GitHub 文件列表可能显示旧版本号：")
            for d in stale:
                r = run(["git", "log", "-1", "--format=%h %s", "--", d])
                print(f"    {d}/ → {r.stdout.strip()}")
            print("  （不影响推送，仅提示）")
        else:
            print(f"✓ 关键目录新鲜度 ok")

    # ── 检查3: GitHub Release ──
    if release_exists(version):
        print(f"✓ GitHub Release {tag} 存在")
    else:
        print(f"✗ GitHub Release {tag} 不存在")
        errors.append("release")

    # ── 汇总 ──
    if not errors:
        print(f"\n✓ 版本一致性检查全部通过 ({version})")
        return 0

    # ── 修复模式 ──
    if fix_mode:
        print(f"\n🔧 自动修复中...")
        if "tag" in errors:
            # 取上次提交的标题作为 tag 消息
            r = run(["git", "log", "-1", "--format=%s"])
            msg = r.stdout.strip()
            run(["git", "tag", "-a", tag, "-m", f"{tag} — {msg}"])
            print(f"  ✓ 已创建标签 {tag}")
            r2 = run(["git", "push", "origin", tag])
            if r2.returncode == 0:
                print(f"  ✓ 已推送标签 {tag}")
            else:
                print(f"  ⚠ 标签推送失败: {r2.stderr.strip()}")

        if "release" in errors:
            # 尝试用最近提交创建 Release（gh CLI 必需）
            r = run(["git", "log", "-1", "--format=%s"])
            title = f"{r.stdout.strip()}"
            r2 = run([
                "gh", "release", "create", tag,
                "--title", f"SOMA {tag}",
                "--notes", f"## {tag}\n\n{title}\n\nAuto-generated by version_guard.py --fix",
            ])
            if r2.returncode == 0:
                print(f"  ✓ 已创建 GitHub Release {tag}")
            else:
                print(f"  ⚠ Release 创建失败: {r2.stderr.strip()}")

        print(f"\n✓ 修复完成，可以推送了")
        return 0

    # ── 阻断推送 ──
    print(f"\n{'─'*50}")
    print(f"⚠ 推送已阻断。缺少: {', '.join(errors)}")
    print(f"  修复: python scripts/version_guard.py --fix")
    print(f"  跳过: git push --no-verify  (不推荐)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
