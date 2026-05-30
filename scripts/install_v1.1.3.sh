#!/bin/bash
set -e

echo "============================================"
echo "  SOMA v1.1.3 中道引擎深化 — 一键安装"
echo "  目标: 零熵智库本地测试"
echo "============================================"
echo ""

cd "$(dirname "$0")/.."

echo "[1/3] 检查 Python 环境..."
python3 --version >/dev/null 2>&1 || { echo "  [错误] 未找到 Python3"; exit 1; }
python3 -c "import sys; assert sys.version_info >= (3,10), '需要 Python 3.10+'" || { echo "  [错误] Python 版本过低"; exit 1; }
echo "  [OK] Python 环境正常"

echo ""
echo "[2/3] 安装 SOMA v1.1.3..."
pip install dist/soma_wisdom-1.1.3-py3-none-any.whl --force-reinstall --quiet 2>/dev/null || \
    pip3 install dist/soma_wisdom-1.1.3-py3-none-any.whl --force-reinstall --quiet
echo "  [OK] SOMA 已安装"

echo ""
echo "[3/3] 验证安装..."
python3 scripts/verify_install.py && echo "" || { echo "  [警告] 部分验证未通过"; exit 1; }

echo "============================================"
echo "  安装完成！"
echo ""
echo "  启动 Dash:  python3 -m soma.dash.server"
echo "  或:         python3 -c \"from soma.dash.server import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8765)\""
echo ""
echo "  导入测试:  python3 -c \"from soma import SOMA; s = SOMA(enable_zhongdao=True, llm='deepseek-chat'); print('OK')\""
echo ""
echo "  详细说明:  docs/SOMA_v1.1.3_测试说明.md"
echo "============================================"
