"""RBAC 访问控制 — 多用户场景下的记忆隔离与权限管理（v1.0.1）

零外部依赖。基于角色（role）和命名空间（namespace）的轻量级访问控制。

用法::

    from soma.rbac import RBACManager

    rbac = RBACManager()
    rbac.create_user("alice", roles=["admin"])
    rbac.create_user("bob", roles=["reader"])
    rbac.grant_namespace("bob", "project_alpha")  # bob 只能读 project_alpha

    if rbac.can_read("alice", "project_alpha"):
        memories = soma.query_memory("...", user_id="alice")
"""

from typing import Dict, List, Optional, Set


class RBACManager:
    """轻量级 RBAC — 内存中的角色-权限-命名空间管理器

    角色层级:
    - admin: 读写所有 namespace + 管理用户
    - writer: 读写指定 namespace
    - reader: 只读指定 namespace
    """

    _ROLE_PERMISSIONS = {
        "admin": {"read", "write", "delete", "manage_users", "manage_roles"},
        "writer": {"read", "write"},
        "reader": {"read"},
    }

    def __init__(self):
        self._users: Dict[str, dict] = {}       # user_id → {roles, namespaces}
        self._namespaces: Set[str] = {"default"}

    # ── 用户管理 ────────────────────────────────────────────────

    def create_user(self, user_id: str, roles: Optional[List[str]] = None, namespaces: Optional[List[str]] = None) -> str:
        """创建用户。返回 user_id。"""
        self._users[user_id] = {
            "roles": set(roles or ["reader"]),
            "namespaces": set(namespaces or ["default"]),
        }
        return user_id

    def delete_user(self, user_id: str) -> bool:
        """删除用户。"""
        return self._users.pop(user_id, None) is not None

    def assign_role(self, user_id: str, role: str) -> bool:
        """为用户分配角色"""
        if user_id not in self._users:
            return False
        if role not in self._ROLE_PERMISSIONS:
            return False
        self._users[user_id]["roles"].add(role)
        return True

    def revoke_role(self, user_id: str, role: str) -> bool:
        """撤销用户角色"""
        if user_id not in self._users:
            return False
        self._users[user_id]["roles"].discard(role)
        return True

    def get_roles(self, user_id: str) -> List[str]:
        """获取用户的角色列表"""
        user = self._users.get(user_id)
        return sorted(user["roles"]) if user else []

    # ── 命名空间管理 ─────────────────────────────────────────────

    def grant_namespace(self, user_id: str, namespace: str) -> bool:
        """授权用户访问某个命名空间"""
        if user_id not in self._users:
            return False
        self._users[user_id]["namespaces"].add(namespace)
        self._namespaces.add(namespace)
        return True

    def revoke_namespace(self, user_id: str, namespace: str) -> bool:
        """撤销用户对命名空间的访问"""
        if user_id not in self._users:
            return False
        if namespace == "default":
            return False
        self._users[user_id]["namespaces"].discard(namespace)
        return True

    def get_namespaces(self, user_id: str) -> List[str]:
        """获取用户可访问的命名空间列表"""
        user = self._users.get(user_id)
        return sorted(user["namespaces"]) if user else []

    # ── 权限检查 ────────────────────────────────────────────────

    def _get_permissions(self, user_id: str) -> Set[str]:
        """获取用户的所有权限（合并所有角色）"""
        user = self._users.get(user_id)
        if not user:
            return set()
        perms = set()
        for role in user["roles"]:
            perms |= self._ROLE_PERMISSIONS.get(role, set())
        return perms

    def can_read(self, user_id: str, namespace: str = "default") -> bool:
        """检查用户是否有读权限"""
        user = self._users.get(user_id)
        if not user:
            return False
        if namespace not in user["namespaces"]:
            return False
        return "read" in self._get_permissions(user_id)

    def can_write(self, user_id: str, namespace: str = "default") -> bool:
        """检查用户是否有写权限"""
        user = self._users.get(user_id)
        if not user:
            return False
        if namespace not in user["namespaces"]:
            return False
        return "write" in self._get_permissions(user_id)

    def can_delete(self, user_id: str, namespace: str = "default") -> bool:
        """检查用户是否有删除权限"""
        user = self._users.get(user_id)
        if not user:
            return False
        if namespace not in user["namespaces"]:
            return False
        return "delete" in self._get_permissions(user_id)

    def can_manage_users(self, user_id: str) -> bool:
        """检查用户是否可以管理其他用户"""
        return "manage_users" in self._get_permissions(user_id)

    # ── 序列化 ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """导出 RBAC 状态为可序列化字典"""
        return {
            "users": {
                uid: {
                    "roles": sorted(u["roles"]),
                    "namespaces": sorted(u["namespaces"]),
                }
                for uid, u in self._users.items()
            },
            "namespaces": sorted(self._namespaces),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RBACManager":
        """从字典恢复 RBAC 状态"""
        rbac = cls()
        rbac._namespaces = set(data.get("namespaces", ["default"]))
        for uid, u in data.get("users", {}).items():
            rbac._users[uid] = {
                "roles": set(u["roles"]),
                "namespaces": set(u["namespaces"]),
            }
        return rbac

    @property
    def user_count(self) -> int:
        return len(self._users)

    @property
    def namespace_count(self) -> int:
        return len(self._namespaces)
