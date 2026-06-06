---
name: learning-library-index
description: 在最终学习资料库外部维护资源索引、去重记录和来源追踪。用于 learning-library-organizer 输出 learning-library-organize/v1 后，更新 JSON 索引、按哈希去重、记录资源分类和检索字段；不负责搜索、评分、下载或把索引写进最终资料库。
---

# 学习资料库外部索引

## 目标

接收 `learning-library-organizer` 的归档结果，在最终资料库外部维护索引，支持后续检索、去重、更新和来源追踪。

本 skill 的边界：

- 索引文件必须放在资料库外部。
- 最终资料库目录只保留真实学习资源文件。
- 不搜索、不评分、不下载、不移动资料库文件。
- 不把索引 JSON、日志、manifest、缓存写进最终资料库。
- 不因为资源类型、主题、格式或来源创建特殊全局规则。

## 输入

输入 `learning-library-organize/v1`：

```json
{
  "organize_schema": "learning-library-organize/v1",
  "organized_files": []
}
```

每个 `organized_files[]` 至少应包含：

- `library_file`
- `original_file`
- `title`
- `format`
- `resource_type`
- `classification`
- `classification_confidence`
- `sha256`

## 输出

输出 `learning-library-index-update/v1`，完整契约见 `references/index-schema.md`。

```json
{
  "index_schema": "learning-library-index-update/v1",
  "status": "completed | partial | failed",
  "index_dir": "",
  "created": 0,
  "updated": 0,
  "duplicates": []
}
```

输出摘要可以写到工作目录或命令行；索引文件也必须位于资料库外部。

## 索引文件

第一版默认维护：

```text
.learning-resource-work/
  index/
    resources.json
    duplicates.json
```

`resources.json` 保存当前资源索引，按 `sha256` 去重。`duplicates.json` 保存重复资源或同哈希多路径记录。

## 使用脚本

```bash
python3 skills/learning-library-index/scripts/update_index.py \
  organize-result.json \
  --index-dir .learning-resource-work/index \
  --library-dir 学习资料库 \
  -o .learning-resource-work/index/index-update-result.json
```

只预览不写入：

```bash
python3 skills/learning-library-index/scripts/update_index.py \
  organize-result.json \
  --dry-run
```

## 去重规则

- 优先使用 `sha256` 作为资源唯一键。
- 同一 `sha256` 已存在且路径相同：更新元数据和 `updated_at`。
- 同一 `sha256` 已存在但路径不同：写入 `duplicates`，不删除文件。
- 缺少 `sha256` 时用 `library_file` 生成弱键，并标记 `dedupe_confidence=low`。
- 第一版只记录重复，不自动删除或移动资料库文件。

## 检索字段

索引应保留以下检索维度：

- 标题
- 文件路径
- 格式
- 资源类型
- 学段或适龄
- 年级或阶段
- 学习领域或学科
- 主题或资源类型
- 来源或版本
- 来源 URL
- 分类置信度
- 是否待确认
- 哈希

后续 `local-library-search` 可以基于该索引做本地资料库检索。
