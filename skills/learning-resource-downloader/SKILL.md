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

如果候选 `requires_auth=true`，默认输出 `skipped`，说明需要登录或授权访问。

当 OpenClaw 已经提供账号态，并且用户确认可以使用该账号态下载时，可显式传入 `--allow-auth`。下载器会读取运行环境中的授权上下文，并尝试候选中的 `source_url` 和 `raw.url_candidates`，但不会把 token、cookie 或 header 原文写入输出。

可用授权环境变量：

```text
SMARTEDU_ACCESS_TOKEN
SMARTEDU_COOKIE
SMARTEDU_AUTHORIZATION
SMARTEDU_HEADERS
```

也可临时传入：

```text
--access-token
--cookie
--header "Name: value"
```

当前只负责下载可直接访问的文件或播放清单。复杂 m3u8 分片合并、DRM、验证码、二次验证和站点专用签名逻辑后续由专门下载适配器扩展。

下载前可先使用 `--probe-only` 探测 URL：

```bash
python3 skills/learning-resource-downloader/scripts/download_selected.py \
  selection.json \
  --select A \
  --allow-auth \
  --probe-only
```

探测模式会按顺序检查 `source_url` 和 `candidate.raw.url_candidates`，输出每个 URL 的 HTTP 状态、内容类型和可访问性，不保存文件。

如果 SmartEdu 私有文件需要浏览器登录态，可以在探测阶段传入浏览器 state：

```bash
python3 skills/learning-resource-downloader/scripts/download_selected.py \
  selection.json \
  --select A \
  --allow-auth \
  --probe-only \
  --browser-state .learning-resource-work/smartedu-browser/state.json
```

`--browser-state` 当前只用于 `--probe-only`。正式下载仍需要明确的 token、cookie、header，或后续专门下载适配器确认签名和过期策略后再执行。

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

使用授权上下文尝试下载 SmartEdu 授权资源：

```bash
SMARTEDU_ACCESS_TOKEN='...' \
python3 skills/learning-resource-downloader/scripts/download_selected.py \
  selection.json \
  --select A \
  --allow-auth
```

## 重要边界

- 下载结果进入工作缓存目录，例如 `.learning-resource-work/downloads/`。
- 最终资料库只能由后续 `learning-library-organizer` 写入。
- token、cookie、manifest、日志不得进入最终资料库。
- 下载 JSON 只能记录 `auth_context=true/false`，不得输出 token、cookie 或 header 原文。
- 浏览器 state 只能作为授权上下文标记和探测输入，不得输出 cookie、localStorage、Authorization、MAC 或 `x-nd-auth` 原文。
- 对大文件、可疑文件、下载器页面、需要登录资源，应跳过或失败记录，不做强行下载。
