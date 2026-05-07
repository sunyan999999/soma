#!/bin/bash
# 零熵智库 v0.7.0 一键诊断+导出
# 用法: bash v070_one_click_export.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${SOMA_DATA_DIR:-$(pwd)/soma_data}"

echo "=== SOMA v0.7.0 一键诊断+导出 ==="
echo "数据目录: $DATA_DIR"
echo ""

# 1. 合并 WAL
echo "[1/3] 合并 WAL 日志..."
cd "$DATA_DIR"
for f in episodic semantic skills evolver analytics; do
    if [ -f "${f}.db" ]; then
        sqlite3 "${f}.db" "PRAGMA wal_checkpoint(TRUNCATE)" 2>/dev/null
        echo "  ${f}.db  OK"
    fi
done

# 2. 运行诊断
echo "[2/3] 运行诊断脚本..."
cd "$SCRIPT_DIR/.."
python scripts/server_diagnostic.py

# 3. 打包
echo "[3/3] 打包..."
cd "$DATA_DIR"
TARBALL="/tmp/soma_data_v070_$(date +%Y%m%d_%H%M%S).tar.gz"
tar czf "$TARBALL" *.db diagnostic_v070.json 2>/dev/null

echo ""
echo "=== 完成 ==="
ls -lh "$TARBALL"
echo ""
echo "请将此文件下载到本地 C:\\SOMA\\ 目录:"
echo "  $TARBALL"
