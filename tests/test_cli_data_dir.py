"""v2.0.38: 迁移类 CLI 的库路径显式参数。

## 背景（下游实测）

`soma semantic-kind` 在生产上 dry-run **扫到 0 行** —— 因为它解析的是
`~/.soma/<project>`，而生产库在 `SOMA_DATA_DIR=/data/.../soma_data`。

「扫描 0 条」看起来像「库里没有要处理的数据」，这是最容易被误读的静默结果。
修法：给迁移类命令加 `--data-dir` / `--db`，并在帮助里明示**不读
SOMA_DATA_DIR**。

## 判据

  · --db 优先于 --data-dir
  · --data-dir 真的决定 persist_dir
  · 帮助文本必须说明「不读 SOMA_DATA_DIR」（否则运维依然会误读）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma.cli import _resolve_data_dir, build_parser


class _Args:
    def __init__(self, data_dir="", db=""):
        self.data_dir = data_dir
        self.db = db


class TestResolveDataDir:
    def test_data_dir_wins_over_project(self):
        assert _resolve_data_dir(_Args(data_dir=r"C:\prod\soma_data")) == r"C:\prod\soma_data"

    def test_db_takes_precedence(self, tmp_path):
        db = tmp_path / "semantic.db"
        db.write_text("", encoding="utf-8")
        got = _resolve_data_dir(_Args(data_dir=r"C:\ignored", db=str(db)))
        assert got == str(tmp_path.resolve())

    def test_nothing_given_returns_empty(self):
        assert _resolve_data_dir(_Args()) == ""


class TestGetSomaUsesDataDir:
    def test_persist_dir_follows_data_dir(self, tmp_path):
        from soma.cli import _get_soma

        target = tmp_path / "prod_like"
        target.mkdir()
        s = _get_soma("", str(target))
        try:
            assert str(s._config.episodic_persist_dir) == str(target), (
                f"persist_dir 没跟随 --data-dir：{s._config.episodic_persist_dir}")
        finally:
            s.close()


class TestParserSurface:
    def _parse(self, argv):
        return build_parser().parse_args(argv)

    @pytest.mark.parametrize("cmd", ["semantic-kind", "reclassify"])
    def test_both_migration_commands_accept_data_dir(self, cmd):
        args = self._parse([cmd, "--data-dir", "/data/soma"])
        assert args.data_dir == "/data/soma"

    @pytest.mark.parametrize("cmd", ["semantic-kind", "reclassify"])
    def test_both_accept_db(self, cmd):
        args = self._parse([cmd, "--db", "/data/soma/semantic.db"])
        assert args.db == "/data/soma/semantic.db"

    def test_help_mentions_soma_data_dir_not_read(self):
        """★ 帮助里必须写明不读 SOMA_DATA_DIR。

        没有这句，运维看到「扫描 0 条」仍会以为是数据问题。
        """
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf), pytest.raises(SystemExit):
            build_parser().parse_args(["semantic-kind", "--help"])
        text = buf.getvalue()

        assert "SOMA_DATA_DIR" in text, (
            "帮助文本没有说明「不读 SOMA_DATA_DIR」——这个静默坑会复发")
        assert "--data-dir" in text
        assert "--db" in text
