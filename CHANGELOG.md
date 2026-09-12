# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [v8] - 最新

### 修复

- 修复删除文件的 Qdrant filter 失效问题：`remove_deleted_from_store` 之前把裸 dict 传给 `points_selector`，Qdrant 不接受该类型，异常被静默吞掉，导致已删除文件的向量残留
- 修复 `indexer.py --force` 时未显式释放 SQLite 句柄的问题：改用 `client.close()` 替代 `del` 引用
- 向量维度从硬编码 512 改为从 `config.EMBEDDING_DIM` 读取

### 新增

- 支持 `.pptx` 文档解析（按页提取文字与表格）
- 支持 `.doc` 文档优雅降级
- 添加 GitHub Actions 自动测试（Python 3.11 / 3.12）
- 添加手动触发的评估 workflow

## [v7]

### 修复

- Index 累积 bug：`indexer.py --force` 时改用 `shutil.rmtree(QDRANT_PATH)` 彻底清理
- Per-source BM25 归一化，防止长文档压制短文档
- Confidence 混合公式：`0.8 * rerank + 0.2 * rrf`
- PDF metadata 保留

### 新增

- 诊断脚本 `src/diagnostic.py`

## [v6]

### 修复

- 指标测量 bug：`context_precision` 和 `context_recall` 改用 parent_text 计算
- 测试集关键词修正

### 效果

- context_precision: 0.65 → 0.9
- context_recall: 0.951 → 1.0
