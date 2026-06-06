---
name: learning-library-organizer
description: 将已下载的学习资源文件识别、规范命名、分类并归档到最终学习资料库。用于 learning-resource-downloader 输出 learning-resource-download/v1 后，把 PDF、DOC、PPT、图片、音频、视频等真实资源文件整理进资料库；不负责搜索、评分、下载或维护长期索引。
---

# 学习资料库归档整理

## 目标

接收 `learning-resource-downloader` 的下载结果，将真实资源文件整理进最终资料库，并输出归档摘要。

本 skill 的边界：

- 只把真实学习资源文件写入最终资料库。
- JSON、manifest、日志、缓存、索引不得写入最终资料库。
- 不搜索、不评分、不下载。
- 不把来源和资源类型硬绑定，分类应基于元数据和文件证据动态判断。
- 低置信度资源进入 `待确认/`，等待后续人工或模型复核。

## 输入

输入 `learning-resource-download/v1`：

```json
{
  "download_schema": "learning-resource-download/v1",
  "downloaded_files": []
}
```

每个 `downloaded_files[]` 至少应包含：

- `local_file`
- `title`
- `format`
- `resource_type`
- `candidate`

## 输出

输出 `learning-library-organize/v1`，完整契约见 `references/organize-schema.md`。

```json
{
  "organize_schema": "learning-library-organize/v1",
  "status": "completed | partial | failed",
  "organized_files": [],
  "failures": []
}
```

输出 JSON 应保存在工作目录、命令输出或外部索引目录，不得放入最终资料库。

## 默认资料库结构

```text
学习资料库/
  学段或适龄/
    年级或阶段/
      学习领域或学科/
        主题或资源类型/
          来源或版本/
            文件名
  待确认/
    格式/
      文件名
```

示例：

```text
学习资料库/小学/三年级/数学/教材/人教版/义务教育教科书_数学三年级上册_33c8d495.pdf
学习资料库/8岁/未分年级/数学/四则混合运算/示例来源/四则混合运算练习题_ab12cd34.pdf
学习资料库/待确认/pdf/未知标题_09af31bc.pdf
```

分类维度可以为空缺，但不能强行编造。缺失关键分类时使用 `未分学段`、`未分年级`、`综合`、`未分主题`；置信度过低时进入 `待确认/`。

## 使用脚本

```bash
python3 skills/learning-library-organizer/scripts/organize_downloads.py \
  download-result.json \
  --library-dir 学习资料库 \
  --work-dir .learning-resource-work \
  -o .learning-resource-work/organize-result.json
```

只预览不写入：

```bash
python3 skills/learning-library-organizer/scripts/organize_downloads.py \
  download-result.json \
  --dry-run
```

## 归档规则

- 默认复制文件，保留下载缓存；需要移动时使用 `--mode move`。
- 文件名使用标题、短哈希和原始扩展名组合，避免覆盖。
- 路径和文件名必须清理非法字符。
- 相同目标路径已存在时自动追加序号。
- 无法读取、不是文件、路径缺失的资源写入 `failures`。
- 最终资料库内不得创建 `.json`、`.log`、`.tmp`、`.manifest`、缓存目录或索引文件。

## 与后续 skill 的关系

`learning-library-index` 后续负责：

- 外部索引。
- 去重记录。
- 资料库更新历史。
- 文件内容摘要和全文检索入口。

这些索引文件必须放在资料库外部，例如 `.learning-resource-work/index/`。
