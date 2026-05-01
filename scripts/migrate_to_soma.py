#!/usr/bin/env python3
"""离线批量注入脚本 — 将外部知识库导入 SOMA 记忆系统

用法:
    # 从 JSON 文件导入
    python scripts/migrate_to_soma.py --input docs.json --format json

    # 从 Markdown/文本目录导入
    python scripts/migrate_to_soma.py --input ./knowledge/ --format text

    # 从 CSV 导入（需含 content, domain, type 列）
    python scripts/migrate_to_soma.py --input data.csv --format csv

    # 干跑（不实际写入）
    python scripts/migrate_to_soma.py --input docs.json --dry-run

输入格式:
    JSON: [{"content": "...", "domain": "...", "type": "...", "importance": 0.8}, ...]
    CSV:  含 content/domain/type 列
    TEXT: 目录中 .md/.txt 文件，按段落拆分
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 确保 soma-core 在路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from soma import SOMA


# ═══════════════════════════════════════════════════════════════
# 三元组自动抽取（轻量 NLP，不依赖 LLM）
# ═══════════════════════════════════════════════════════════════

# 中文谓词模式：A 是 B / A 包含 B / A 影响 B / A 依赖于 B
_PREDICATE_PATTERNS = [
    (re.compile(r"([一-鿿\w]{2,20})是([一-鿿\w]{2,20})的([一-鿿\w]{2,20})"), "是...的"),
    (re.compile(r"([一-鿿\w]{2,20})包含([一-鿿\w]{2,20})"), "包含"),
    (re.compile(r"([一-鿿\w]{2,20})影响([一-鿿\w]{2,20})"), "影响"),
    (re.compile(r"([一-鿿\w]{2,20})依赖于([一-鿿\w]{2,20})"), "依赖于"),
    (re.compile(r"([一-鿿\w]{2,20})导致([一-鿿\w]{2,20})"), "导致"),
    (re.compile(r"([一-鿿\w]{2,20})需要([一-鿿\w]{2,20})"), "需要"),
    (re.compile(r"([一-鿿\w]{2,20})与([一-鿿\w]{2,20})(相关|关联|共生|协同)"), "与...相关"),
    (re.compile(r"([一-鿿\w]{2,20})可分为([一-鿿\w]{2,20})"), "可分为"),
    (re.compile(r"([一-鿿\w]{2,20})体现了([一-鿿\w]{2,20})"), "体现了"),
    (re.compile(r"([一-鿿\w]{2,20})作用于([一-鿿\w]{2,20})"), "作用于"),
]


def extract_triples(text: str, max_triples: int = 5) -> List[Tuple[str, str, str]]:
    """从文本中抽取简单三元组（正则匹配）"""
    triples: List[Tuple[str, str, str]] = []
    seen: set = set()
    for pattern, predicate in _PREDICATE_PATTERNS:
        for m in pattern.finditer(text):
            groups = m.groups()
            if len(groups) == 3:
                subj, obj = groups[0], groups[2]
            else:
                subj, obj = groups[0], groups[1]
            key = (subj, predicate, obj)
            if key not in seen and subj != obj:
                seen.add(key)
                triples.append(key)
            if len(triples) >= max_triples:
                return triples
    return triples


# ═══════════════════════════════════════════════════════════════
# 段落拆分
# ═══════════════════════════════════════════════════════════════

def split_paragraphs(text: str, min_len: int = 50) -> List[str]:
    """按空行拆分为段落，过滤太短的"""
    raw = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in raw if len(p.strip()) >= min_len]


def parse_text_file(filepath: Path) -> List[Dict[str, Any]]:
    """解析单个文本/markdown文件为记录列表"""
    try:
        text = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = filepath.read_text(encoding="gbk", errors="ignore")

    paragraphs = split_paragraphs(text)
    domain = filepath.stem  # 文件名作为默认领域
    records = []
    for i, para in enumerate(paragraphs):
        records.append({
            "content": para[:2000],  # 截断到2000字符
            "domain": domain,
            "type": "article_segment",
            "importance": max(0.3, 0.8 - i * 0.05),  # 越靠前越重要
        })
    return records


# ═══════════════════════════════════════════════════════════════
# 批量注入
# ═══════════════════════════════════════════════════════════════

def migrate(
    soma: SOMA,
    records: List[Dict[str, Any]],
    extract_triples_enabled: bool = True,
    dry_run: bool = False,
    verbose: bool = True,
) -> Dict[str, int]:
    """批量注入记忆"""
    stats = {"episodic": 0, "semantic_triples": 0, "errors": 0}
    total = len(records)

    for i, record in enumerate(records):
        content = record.get("content", "")
        if not content.strip():
            continue

        domain = record.get("domain", "imported")
        mem_type = record.get("type", "imported_note")
        importance = float(record.get("importance", 0.5))

        try:
            if not dry_run:
                soma.remember(
                    content=content,
                    context={"domain": domain, "type": mem_type},
                    importance=importance,
                )
            stats["episodic"] += 1

            # 自动抽取三元组
            if extract_triples_enabled and len(content) >= 100:
                triples = extract_triples(content)
                for subj, pred, obj in triples:
                    try:
                        if not dry_run:
                            soma.remember_semantic(subj, pred, obj)
                        stats["semantic_triples"] += 1
                    except Exception:
                        stats["errors"] += 1

            if verbose and (i + 1) % 10 == 0:
                pct = (i + 1) / total * 100
                print(f"  进度: {i+1}/{total} ({pct:.0f}%) — 情节 {stats['episodic']}, 三元组 {stats['semantic_triples']}")

        except Exception as e:
            stats["errors"] += 1
            if verbose:
                print(f"  ⚠ 第 {i+1} 条导入失败: {e}")

    return stats


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def load_records(input_path: str, fmt: str) -> List[Dict[str, Any]]:
    """按格式加载记录"""
    path = Path(input_path)
    records = []

    if fmt == "json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and "records" in data:
            records = data["records"]

    elif fmt == "csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            records = list(reader)

    elif fmt == "text":
        if path.is_dir():
            for fpath in sorted(path.rglob("*.md")) + sorted(path.rglob("*.txt")):
                records.extend(parse_text_file(fpath))
        else:
            records = parse_text_file(path)

    else:
        print(f"不支持的格式: {fmt}，可选: json, csv, text")
        sys.exit(1)

    return records


def main():
    parser = argparse.ArgumentParser(
        description="SOMA 离线批量注入 — 将外部知识库导入记忆系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --input knowledge_base.json --format json
  %(prog)s --input ./articles/ --format text --dry-run
  %(prog)s --input data.csv --format csv --no-triples
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="输入文件或目录路径")
    parser.add_argument("--format", "-f", choices=["json", "csv", "text"], default="json",
                        help="输入格式 (默认: json)")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际写入")
    parser.add_argument("--no-triples", action="store_true", help="不自动抽取三元组")
    parser.add_argument("--data-dir", help="SOMA 数据目录（默认取其环境变量或默认值）")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式")
    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        print(f"输入路径不存在: {input_path}")
        sys.exit(1)

    # 加载
    print(f"📂 加载数据: {input_path} (格式: {args.format})")
    records = load_records(input_path, args.format)
    if not records:
        print("没有找到可导入的记录")
        sys.exit(0)
    print(f"   共 {len(records)} 条记录")

    # 初始化 SOMA
    soma_kwargs = {}
    if args.data_dir:
        soma_kwargs["persist_dir"] = Path(args.data_dir)
    soma = SOMA(**soma_kwargs)

    # 注入前统计
    before_episodic = soma.memory.episodic.count()
    before_semantic = soma.memory.semantic.count_triples()

    # 执行注入
    label = "🏃 预览 (--dry-run)" if args.dry_run else "🏃 批量注入"
    print(f"\n{label}...")
    start = time.time()
    stats = migrate(
        soma, records,
        extract_triples_enabled=not args.no_triples,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )
    elapsed = time.time() - start

    # 报告
    after_episodic = before_episodic if args.dry_run else soma.memory.episodic.count()
    after_semantic = before_semantic if args.dry_run else soma.memory.semantic.count_triples()

    print(f"\n{'='*50}")
    print(f"  {'预览' if args.dry_run else '注入'}完成 ({elapsed:.1f}s)")
    print(f"  情节记忆: {before_episodic} → {after_episodic} (+{stats['episodic']})")
    print(f"  语义三元组: {before_semantic} → {after_semantic} (+{stats['semantic_triples']})")
    if stats["errors"]:
        print(f"  ⚠ 错误: {stats['errors']} 条")
    print(f"{'='*50}")

    soma.close()


if __name__ == "__main__":
    main()
