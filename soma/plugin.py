"""插件发现与注册 — 基于 Python entry_points 的自动发现机制"""

import sys
from typing import Any, Callable, Dict, List, Optional

if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points, EntryPoint
else:
    from importlib_metadata import entry_points, EntryPoint

# 支持的 entry_point 组名
_KNOWN_GROUPS = {
    "soma.frameworks": "自定义思维框架引擎",
    "soma.stores": "自定义记忆存储后端",
    "soma.embedders": "自定义嵌入模型",
    "soma.llms": "自定义大语言模型",
    "soma.hooks": "自定义生命周期钩子",
}


def discover(group: str) -> List["EntryPoint"]:
    """发现指定组下的所有已注册插件入口。

    返回 importlib.metadata.EntryPoint 对象列表，
    调用 .load() 获取实际对象。

    示例::

        for ep in discover("soma.frameworks"):
            engine = ep.load()()
            agent.engine = engine
    """
    eps = entry_points()
    if hasattr(eps, "select"):
        return list(eps.select(group=group))
    # Python 3.9 兼容：手动过滤
    return [ep for ep in eps if ep.group == group]


def discover_all() -> Dict[str, List["EntryPoint"]]:
    """发现所有已知 SOMA 插件组的入口。

    返回 {group_name: [EntryPoint, ...]} 映射。
    """
    result: Dict[str, List[EntryPoint]] = {}
    for group in _KNOWN_GROUPS:
        found = discover(group)
        if found:
            result[group] = found
    return result


def load_plugin(group: str, name: str) -> Optional[Any]:
    """按名称加载指定插件。

    示例::

        framework = load_plugin("soma.frameworks", "my_framework")
        if framework:
            agent.engine = framework()
    """
    for ep in discover(group):
        if ep.name == name:
            return ep.load()
    return None


def list_plugins() -> Dict[str, List[str]]:
    """列出所有已发现的插件名称。

    返回 {group_name: [plugin_name, ...]} 映射。
    """
    result: Dict[str, List[str]] = {}
    for group, desc in _KNOWN_GROUPS.items():
        names = [ep.name for ep in discover(group)]
        if names:
            result[group] = names
    return result


# entry_point 注册工厂 — 供插件包在 pyproject.toml 中引用

def create_framework_factory(cls: type) -> Callable:
    """包装框架引擎类为无参工厂函数"""
    def factory():
        return cls()
    return factory


def create_store_factory(cls: type) -> Callable:
    """包装存储类为无参工厂函数"""
    def factory():
        return cls()
    return factory


def create_embedder_factory(cls: type) -> Callable:
    """包装嵌入器类为无参工厂函数"""
    def factory():
        return cls()
    return factory


def create_llm_factory(cls: type) -> Callable:
    """包装 LLM 类为无参工厂函数"""
    def factory():
        return cls()
    return factory
