---
name: learning-resource-downloader
description: 根据用户在候选清单中的选择下载学习资源到工作缓存目录。用于 selector 输出 learning-resource-selection/v1 且用户选择 A/B/C 后，下载 PDF、DOC、PPT、图片、网页快照等可访问资源；不负责搜索、评分、最终归档或资料库整理。
---

# 学习资源下载缓存

## 目标

接收 `learning-resource-selector` 输出的候选清单和用户选择，将可下载资源保存到工作缓存目录，并输出标准下载结果。

本 skill 只负责下载到工作缓存：

- 不写入最终资料库。
- 不做分类归档。
- 不维护长期索引。
- 不绕过登录、付费、版权或访问限制。

## 输入

输入 `learning-resource-selection/v1` 和用户选择：

```json
{
  "selection_schema": "learning-resource-selection/v1",
  "options": []
}
```

用户选择可以是：

- `A`
- `A,B`
- `all`
- `官方`
- `PDF`

第一版脚本支持明确编号和 `all`。

## 输出

输出 `learning-resource-download/v1`，完整契约见 `references/download-schema.md`。

```json
{
  "download_schema": "learning-resource-download/v1",
  "status": "completed | partial | failed",
  "downloaded_files": [],
  "skipped": [],
  "failures": []
}
```

## 下载策略

### 可直接下载

满足以下条件时可以尝试直接下载：

- 候选 `downloadable=true`。
- 有 `source_url`。
- 不需要登录或授权。
- URL 或格式显示为普通文件：PDF、DOC/DOCX、PPT/PPTX、图片、音频、视频、压缩包等。

### 网页资源

如果资源格式是 `html` 或不可判断为文件，第一版保存 HTML 快照。快照仍进入工作缓存，不进入最终资料库。

### 需要授权或专用流程

如果候选 `requires_auth=true`，或来源需要专用下载流程，第一版不在通用 downloader 里硬编码来源逻辑，而是输出 `skipped`，说明需要专用 source 下载器或授权信息。

## 使用脚本

```bash
python3 skills/learning-resource-downloader/scripts/download_selected.py \
  selection.json \
  --select A,B \
  --work-dir .learning-resource-work
```

下载全部展示选项：

```bash
python3 skills/learning-resource-downloader/scripts/download_selected.py \
  selection.json \
  --select all
```

## 重要边界

- 下载结果进入工作缓存目录，例如 `.learning-resource-work/downloads/`。
- 最终资料库只能由后续 `learning-library-organizer` 写入。
- token、cookie、manifest、日志不得进入最终资料库。
- 对大文件、可疑文件、下载器页面、需要登录资源，应跳过或失败记录，不做强行下载。
