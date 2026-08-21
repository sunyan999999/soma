# -*- coding: utf-8 -*-
"""RBAC 访问控制测试 — v1.0.1"""
from soma.rbac import RBACManager


def test_create_user_default_reader():
    rbac = RBACManager()
    rbac.create_user("alice")
    assert rbac.user_count == 1
    assert rbac.get_roles("alice") == ["reader"]
    assert rbac.get_namespaces("alice") == ["default"]


def test_create_user_with_roles_and_namespaces():
    rbac = RBACManager()
    rbac.create_user("alice", roles=["admin", "writer"], namespaces=["proj1"])
    assert rbac.get_roles("alice") == ["admin", "writer"]
    # create_user 的 namespaces 替换默认，不合并（grant_namespace 才注册到全局）
    assert rbac.get_namespaces("alice") == ["proj1"]


def test_delete_user():
    rbac = RBACManager()
    rbac.create_user("alice")
    assert rbac.delete_user("alice") is True
    assert rbac.delete_user("nonexistent") is False
    assert rbac.user_count == 0


def test_assign_and_revoke_role():
    rbac = RBACManager()
    rbac.create_user("alice", roles=["reader"])
    assert rbac.assign_role("alice", "writer") is True
    assert "writer" in rbac.get_roles("alice")
    # 无效角色
    assert rbac.assign_role("alice", "superadmin") is False
    # 不存在用户
    assert rbac.assign_role("ghost", "writer") is False
    assert rbac.revoke_role("alice", "writer") is True
    assert "writer" not in rbac.get_roles("alice")


def test_grant_revoke_namespace():
    rbac = RBACManager()
    rbac.create_user("alice")
    assert rbac.grant_namespace("alice", "proj1") is True
    assert "proj1" in rbac.get_namespaces("alice")
    # default 不可撤销
    assert rbac.revoke_namespace("alice", "default") is False
    assert rbac.revoke_namespace("alice", "proj1") is True
    assert "proj1" not in rbac.get_namespaces("alice")
    # 不存在用户
    assert rbac.grant_namespace("ghost", "proj1") is False


def test_permissions_by_role():
    rbac = RBACManager()
    rbac.create_user("admin", roles=["admin"])
    rbac.create_user("writer", roles=["writer"])
    rbac.create_user("reader", roles=["reader"])
    # admin 全权限
    assert rbac.can_read("admin")
    assert rbac.can_write("admin")
    assert rbac.can_delete("admin")
    assert rbac.can_manage_users("admin")
    # writer 可读可写不可删
    assert rbac.can_read("writer")
    assert rbac.can_write("writer")
    assert not rbac.can_delete("writer")
    assert not rbac.can_manage_users("writer")
    # reader 只读
    assert rbac.can_read("reader")
    assert not rbac.can_write("reader")


def test_namespace_isolation():
    rbac = RBACManager()
    rbac.create_user("alice", roles=["writer"], namespaces=["proj1"])
    # 有 proj1 访问权
    assert rbac.can_write("alice", "proj1")
    # 无 proj2 访问权（未授权）
    assert not rbac.can_read("alice", "proj2")


def test_unknown_user_no_permission():
    rbac = RBACManager()
    assert not rbac.can_read("ghost")
    assert not rbac.can_write("ghost")
    assert not rbac.can_delete("ghost")
    assert not rbac.can_manage_users("ghost")


def test_serialize_roundtrip():
    rbac = RBACManager()
    rbac.create_user("alice", roles=["admin"], namespaces=["proj1"])
    rbac.grant_namespace("alice", "proj2")  # 注册 proj2 到全局
    rbac.create_user("bob", roles=["reader"])
    data = rbac.to_dict()
    restored = RBACManager.from_dict(data)
    assert restored.user_count == 2
    assert restored.namespace_count == 2  # default + proj2（proj1 仅授权未注册）
    assert restored.get_roles("alice") == ["admin"]
    assert restored.can_read("alice", "proj1")
    assert restored.can_read("alice", "proj2")
    assert restored.can_read("bob")


def test_namespace_count():
    rbac = RBACManager()
    assert rbac.namespace_count == 1  # 默认 default
    rbac.create_user("alice", namespaces=["proj1"])  # 仅授权不注册
    assert rbac.namespace_count == 1
    rbac.grant_namespace("alice", "proj2")  # grant 才注册到全局
    assert rbac.namespace_count == 2  # default + proj2
