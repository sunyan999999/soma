# -*- coding: utf-8 -*-
"""插件发现与注册测试"""
from unittest.mock import patch, MagicMock

from soma import plugin


class _FakeEntryPoint:
    def __init__(self, name, group="soma.frameworks"):
        self.name = name
        self.group = group

    def load(self):
        return lambda: object()


def _fake_select(group):
    return [_FakeEntryPoint("fw_a", group), _FakeEntryPoint("fw_b", group)]


@patch("soma.plugin.entry_points")
def test_discover_select(mock_eps):
    """有 select 方法时用 select 过滤"""
    mock_select = MagicMock(return_value=[_FakeEntryPoint("fw_a")])
    mock_eps.return_value = MagicMock(select=mock_select)
    result = plugin.discover("soma.frameworks")
    assert len(result) == 1
    mock_select.assert_called_once_with(group="soma.frameworks")


@patch("soma.plugin.entry_points")
def test_discover_legacy_iterable(mock_eps):
    """Python 3.9 兼容：无 select 时手动过滤"""
    eps = [_FakeEntryPoint("fw_a", "soma.frameworks"),
           _FakeEntryPoint("store_x", "soma.stores")]
    # 模拟无 select 属性的旧式返回
    mock_eps.return_value = iter(eps)
    result = plugin.discover("soma.frameworks")
    assert len(result) == 1
    assert result[0].name == "fw_a"


@patch("soma.plugin.discover")
def test_discover_all(mock_discover):
    mock_discover.return_value = [_FakeEntryPoint("fw_a")]
    result = plugin.discover_all()
    # discover 对每个已知组被调用
    assert "soma.frameworks" in result
    assert len(result["soma.frameworks"]) == 1


@patch("soma.plugin.discover")
def test_load_plugin_found(mock_discover):
    mock_discover.return_value = [_FakeEntryPoint("fw_a")]
    loaded = plugin.load_plugin("soma.frameworks", "fw_a")
    assert loaded is not None
    # 加载返回的对象可调用（工厂）
    assert callable(loaded)


@patch("soma.plugin.discover")
def test_load_plugin_not_found(mock_discover):
    mock_discover.return_value = [_FakeEntryPoint("fw_a")]
    assert plugin.load_plugin("soma.frameworks", "nonexistent") is None


@patch("soma.plugin.discover")
def test_list_plugins(mock_discover):
    mock_discover.return_value = [_FakeEntryPoint("fw_a"), _FakeEntryPoint("fw_b")]
    result = plugin.list_plugins()
    assert "soma.frameworks" in result
    assert result["soma.frameworks"] == ["fw_a", "fw_b"]


def test_create_factories():
    class Dummy:
        pass

    fw = plugin.create_framework_factory(Dummy)
    assert isinstance(fw(), Dummy)

    store = plugin.create_store_factory(Dummy)
    assert isinstance(store(), Dummy)

    emb = plugin.create_embedder_factory(Dummy)
    assert isinstance(emb(), Dummy)

    llm = plugin.create_llm_factory(Dummy)
    assert isinstance(llm(), Dummy)
