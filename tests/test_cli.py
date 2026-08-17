# -*- coding: utf-8 -*-
"""soma.cli 的单元测试 — 聚焦 --project 命名空间路由。

核心行为：不带 --project 走共享库 (~/.soma/shared/)，带 --project X 走项目库
(~/.soma/X/)，实现「项目记忆」与「跨智能体共享记忆」的隔离。
"""
import argparse
from pathlib import Path
from unittest import mock

import pytest

from soma import cli


def test_persist_dir_defaults_to_shared():
    """空 project 回退到共享库"""
    assert cli._persist_dir("") == cli.SHARED_MEMORY_DIR
    assert cli._persist_dir() == cli.SHARED_MEMORY_DIR


def test_persist_dir_routes_to_project():
    """非空 project 路由到项目隔离库"""
    assert cli._persist_dir("SOMA") == str(Path.home() / ".soma" / "SOMA")


def test_get_soma_routes_persist_dir():
    """_get_soma 把 project 正确映射为 persist_dir"""
    with mock.patch("soma.SOMA") as MockSOMA:
        cli._get_soma("SOMA")
        assert MockSOMA.call_args.kwargs["persist_dir"] == (
            str(Path.home() / ".soma" / "SOMA")
        )

    with mock.patch("soma.SOMA") as MockSOMA:
        cli._get_soma("")
        assert MockSOMA.call_args.kwargs["persist_dir"] == cli.SHARED_MEMORY_DIR


def test_parser_project_defaults_empty():
    """不带 --project 时 project 为空串"""
    p = cli.build_parser()
    assert p.parse_args(["stats"]).project == ""


def test_parser_project_flag_on_recall():
    """recall 子命令解析 --project 与位置参数 query"""
    p = cli.build_parser()
    args = p.parse_args(["recall", "--project", "SOMA", "铁律 约束"])
    assert args.project == "SOMA"
    assert args.query == "铁律 约束"


def test_parser_project_flag_on_record():
    """record 子命令解析 --project / --importance"""
    p = cli.build_parser()
    args = p.parse_args(
        ["record", "--project", "SOMA", "-i", "0.9", "决定: X"]
    )
    assert args.project == "SOMA"
    assert args.importance == 0.9
    assert args.content == "决定: X"


def test_parser_all_commands_accept_project():
    """所有子命令都支持 --project"""
    p = cli.build_parser()
    for cmd in ["recall", "record", "think", "stats", "health",
                "maintain", "learn", "graph"]:
        extra = {"recall": "query", "record": "content",
                 "think": "problem", "learn": "content"}.get(cmd, "")
        argv = [cmd, "--project", "SOMA"]
        if extra:
            argv.append(extra)
        assert p.parse_args(argv).project == "SOMA", f"{cmd} 未支持 --project"


def test_persist_dir_rejects_path_traversal():
    """--project 传路径穿越值必须被拒绝"""
    for bad in ["..", "../shared", "..\\..", "a/b", "a\\b", ".", "/", "C:\\x"]:
        with pytest.raises(ValueError):
            cli._persist_dir(bad)


def test_persist_dir_accepts_valid_names():
    """合法项目名（大写/下划线/连字符）正常路由"""
    assert cli._persist_dir("SOMA") == str(Path.home() / ".soma" / "SOMA")
    assert cli._persist_dir("u1_agent_industry") == (
        str(Path.home() / ".soma" / "u1_agent_industry")
    )
    assert cli._persist_dir("LingshangWorkspace") == (
        str(Path.home() / ".soma" / "LingshangWorkspace")
    )


def test_record_clamps_importance():
    """importance 越界值被 clamp 到 [0,1]"""
    with mock.patch.object(cli, "_get_soma") as mock_get:
        mock_soma = mock.MagicMock()
        mock_soma.remember.return_value = "test-id"
        mock_get.return_value = mock_soma

        cli.cmd_record(argparse.Namespace(
            content="测试内容", importance=999.0, domain="", project=""))
        assert mock_soma.remember.call_args.kwargs["importance"] == 1.0

        cli.cmd_record(argparse.Namespace(
            content="测试内容", importance=-5.0, domain="", project=""))
        assert mock_soma.remember.call_args.kwargs["importance"] == 0.0
