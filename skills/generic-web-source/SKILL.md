---
name: generic-web-source
description: 从简单资源站页面或 site-profile/v1 画像中抽取可直接访问的学习资源直链，并输出 learning-resource-candidate/v1 候选。适用于 PDF、DOC/DOCX、PPT/PPTX、图片、音频、视频、压缩包等直接链接；不下载、不评分、不写资料库。
---

# 通用网页资源来源

## 目标

本 skill 是一个通用 source skill，用于处理 `web-resource-profiler` 判定为 `generic_extract` 的简单资源站。

它只做一件事：把页面或站点画像里的资源直链转换为统一候选资源 `learning-resource-candidate/v1`，交给后续 `learning-resource-analyzer`、`learning-resource-ranker` 和 `learning-resource-selector`。

## 适用场景

- 页面中已经有明确文件链接，例如 PDF、DOCX、PPTX、图片、音频、视频、ZIP。
- `web-resource-profiler` 输出的 `resource_links` 不为空。
- 来源不需要专门 API 解析、登录流程、分页递归或媒体流解析。

## 不适用场景

- SPA/API 结构复杂，需要独立 source skill。
- 资源藏在登录后接口、付费页、播放器、m3u8 或复杂脚本中。
- 只有普通网页文章，没有明确资源文件直链。
- 需要下载文件、验证文件内容或更新资料库。

## 输入

优先使用 `site-profile/v1`：

```bash
python3 skills/generic-web-source/scripts/extract_candidates.py \
  --site-profile-json site-profile.json \
  -o generic-candidates.json
```

也可以用于本地 HTML 调试：

```bash
python3 skills/generic-web-source/scripts/extract_candidates.py \
  --url https://example.edu.cn/resources \
  --html-file sample.html \
  -o generic-candidates.json
```

## 输出

输出标准候选：

```text
learning-resource-candidate/v1
```

候选中的 `source_url` 使用具体资源直链，原始页面地址放入 `raw.origin_page_url`。

## 调用位置

在总流程中应放在：

```text
web-learning-search
  -> resource-source-discovery
  -> web-resource-profiler
  -> generic-web-source
  -> learning-resource-analyzer
  -> learning-resource-ranker
```

如果 profiler 判断 `crawl_strategy=dedicated_source_skill` 或 `profile_deeper`，不要强行使用本 skill，应交给独立 source skill 或继续结构分析。

## 边界

- 不下载资源。
- 不写最终资料库。
- 不写索引。
- 不替代 analyzer/ranker。
- 不处理 token、cookie、登录态或播放器流。
