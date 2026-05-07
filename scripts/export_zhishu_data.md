# 零熵智库 SOMA 数据导出指南

## 目标

将零熵智库服务器上的 SOMA 数据库完整导出，供本地开发测试使用。

## 步骤

### 1. 关闭 SOMA 服务（或至少确保无写入）

```bash
# 如果用的 systemd
sudo systemctl stop soma

# 或者直接杀进程
pkill -f "dash/server.py"
```

### 2. 合并 WAL 日志到主数据库

```bash
cd ~/.soma/soma-core   # 或你的 SOMA_DATA_DIR 路径

for f in episodic semantic skills evolver analytics; do
    echo "处理 ${f}.db..."
    sqlite3 ${f}.db "PRAGMA wal_checkpoint(TRUNCATE)"
done

echo "WAL 合并完成"
```

### 3. 打包数据库文件

```bash
tar czf /tmp/soma_data_$(date +%Y%m%d).tar.gz *.db
ls -lh /tmp/soma_data_$(date +%Y%m%d).tar.gz
```

### 4. 下载到本地

将 `/tmp/soma_data_20260507.tar.gz` 下载，放到 `C:\SOMA\` 目录下，告诉我文件名即可。

### 5. 重启服务（别忘了）

```bash
sudo systemctl start soma
# 或
SOMA_API_KEY=your-key nohup python dash/server.py &
```

## 预期文件大小

| 文件 | 预估大小 |
|------|:--:|
| episodic.db | 80-100MB |
| semantic.db | 4-5MB |
| skills.db | 400-500KB |
| evolver.db | 100-150KB |
| analytics.db | 8-10MB |
| **打包后** | **约 45-50MB** |

有问题随时沟通。
