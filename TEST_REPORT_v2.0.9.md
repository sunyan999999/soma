# TEST_REPORT — SOMA v2.0.9

> 生成日期：2026-08-18
> 版本：v2.0.9（外部知识准确度/质量/过滤）

## 测试结果总览

| 轮次 | 通过 | 失败 | 耗时 |
|------|------|------|------|
| 第 1 轮 | 788 | 0 | 102.02s |
| 第 2 轮 | 789 | 0 | 111.53s |

> 叠加 v2.0.8 阶段 2 轮（763/763）与 v2.0.7 阶段 3 轮（759/760/760），本项目累计 8 轮全量测试零回归。

## 测试环境

- Python 3.13.9
- pytest 8.4.2 + pluggy 1.5.0
- fastembed 0.7.4（锁定）/ litellm 1.96.x（锁定）
- 平台：Windows 11 Home China 10.0.26200

## 本次改动摘要

### 新增能力
- **来源可信度分级** (`soma/source_trust.py`): 域名白名单/黑名单 + 信誉分，黑名单直接拒绝
- **内容质量检测** (`soma/content_quality.py`): 信息密度/重复率/营销词/空话/噪音，可选 LLM 增强
- **事实印证层**: 与已有记忆交叉验证，孤立事实降级
- **严格度三档**: strict/balanced/permissive + SOMAConfig 配置组
- **CLI `--strictness`**: `soma learn --strictness strict`

### 修复
- **冲突检测静默失效**: 补 `SemanticStore.get_all_triples()`（生产环境从不工作）
- **风格样本静默失效**: 补 `EpisodicStore.get_style_samples()`（样本永远为空）
- **弱 context 误拒**: problem_context 拆出的 Foci 与内容零命中时，回退用内容本身拆解

### 变更
- URL 正文提取增强（跳过导航/页脚/广告）
- 知识门控管道 五层 → 七层

## 新增测试

- `tests/test_source_trust.py`: 7 个（白名单/黑名单/子域/未知/自定义配置）
- `tests/test_content_quality.py`: 11 个（正常/营销/空话/过短/LLM回退）
- `tests/test_knowledge_gate.py`: +11（内容质量层/来源过滤/事实印证/严格度/context回退）

## 回归风险

- 全部向后兼容：新层默认阈值不破坏既有接受行为（min_quality=0.40、min_corroboration=0.0、strictness=balanced）
- 语义隔离、多智能体、核心检索路径未改动
