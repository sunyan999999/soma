# SOMA 开发记忆助手 — Shell 集成
# 用法: source shell_setup.sh
# 或添加到 ~/.bashrc / ~/.zshrc 中永久生效

_SOMA_SCRIPT="$(dirname "$0")/dev_memory.py"
# 如果 examples 不在 PATH 中，改用绝对路径:
# _SOMA_SCRIPT="c:/SOMA/soma-core/examples/dev_memory.py"

# 快捷命令
alias soma-save='python "$_SOMA_SCRIPT" save'
alias soma-recall='python "$_SOMA_SCRIPT" recall'
alias soma-ask='python "$_SOMA_SCRIPT" ask'
alias soma-list='python "$_SOMA_SCRIPT" list'
alias soma-stats='python "$_SOMA_SCRIPT" stats'

# 带自动项目检测的包装函数
soma-remember() {
  local proj=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
  python "$_SOMA_SCRIPT" save --project "$proj" "$@"
}

echo "[SOMA] 开发记忆命令已就绪: soma-save | soma-recall | soma-ask | soma-list | soma-stats"
echo "[SOMA] 持久化目录: ~/.soma/dev_memory/"
echo "[SOMA] 示例: soma-save '支付状态机不能跳过 pending_confirm 状态'"
