---
name: learning-resource-analyzer
description: 对学习资源候选做格式识别、详情解析和内容证据提取。用于 source skill 搜索到 PDF、DOC/DOCX、PPT/PPTX、图片、音频、视频、网页等候选后，在评分前补充标题、正文摘要、文件页数、媒体元数据、风险提示和分析置信度；不负责搜索、评分、下载入库。
---

# 学习资源详情分析

## 目标

接收 source skill 返回的候选资源，对候选做轻量详情分析，补充可被 `learning-resource-ranker` 使用的证据。

本 skill 位于 source skill 和 ranker 之间：

```text
source skills -> learning-resource-analyzer -> learning-resource-ranker
```

它不负责搜索、不做最终评分、不写入最终资料库。需要临时读取或下载的文件只能进入工作缓存目录。

## 输入

优先接收 `learning-resource-candidate/v1`：

```json
{
  "candidate_schema": "learning-resource-candidate/v1",
  "candidates": []
}
```

候选可以包含：

- `source_url`：远程 URL。
- `local_file` 或 `file_path`：本地缓存文件。
- `format`：pdf、docx、pptx、image、audio、video、html 等。
- `title`、`description`、`raw`：搜索阶段已有元数据。

## 输出

输出 `learning-resource-analysis/v1`。完整契约见 `references/analysis-schema.md`。

核心结构：

```json
{
  "analysis_schema": "learning-resource-analysis/v1",
  "candidate_schema": "learning-resource-candidate/v1",
  "candidates": [
    {
      "title": "",
      "format": "",
      "raw": {
        "analysis": {
          "analyzed": true,
          "analysis_type": "document | webpage | image | audio | video | unknown",
          "signals": {},
          "text_sample": "",
          "warnings": [],
          "analysis_confidence": 0.0
        }
      }
    }
  ]
}
```

## 分析策略

### 文档类

PDF、DOC/DOCX、PPT/PPTX、TXT、HTML：

- 识别文件格式。
- 提取可用文本样本。
- 估计页数、幻灯片数、段落数或文本长度。
- 判断是否可能是练习、课件、教材、百科文章、音频/视频页面。
- 标记空文件、无法解析、标题缺失、文件过小等风险。

### 图片类

第一版只做轻量元数据：

- 格式、文件大小。
- 如果环境有图像库，可提取宽高。
- OCR 留给后续增强，不在第一版强依赖。

### 音频类

第一版只做轻量元数据：

- 格式、文件大小。
- 如环境有 `ffprobe`，可提取时长。
- 转写留给后续专门能力，不在第一版强依赖。

### 视频类

第一版只做轻量元数据：

- 格式、文件大小。
- 如环境有 `ffprobe`，可提取时长、分辨率。
- 字幕、封面理解、视频内容理解留给后续增强。

### 网页类

- 从 HTML 提取标题、正文文本样本。
- 标记广告、下载器、登录/付费、成人化等风险词。
- 不执行页面中的脚本，不绕过访问限制。

## 使用脚本

分析候选 JSON：

```bash
python3 skills/learning-resource-analyzer/scripts/analyze_candidates.py input.json
```

从标准输入读取：

```bash
python3 skills/learning-resource-analyzer/scripts/analyze_candidates.py - < candidates.json
```

输出到文件：

```bash
python3 skills/learning-resource-analyzer/scripts/analyze_candidates.py input.json -o analyzed.json
```

默认只分析本地文件和已有元数据。需要远程抓取页面或文件头时，显式使用：

```bash
python3 skills/learning-resource-analyzer/scripts/analyze_candidates.py input.json --fetch-remote
```

## 重要边界

- 不下载大文件到最终资料库。
- 不把临时 JSON、日志、缓存放进最终资料库。
- 不把无法证明的信息写入候选字段；不确定的内容放进 `raw.analysis.warnings`。
- 分析结果是评分证据，不是最终推荐结论。
