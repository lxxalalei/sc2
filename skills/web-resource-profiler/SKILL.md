---
name: web-resource-profiler
description: 对 resource-source-discovery 选出的高价值资源站做结构分析，识别页面类型、HTML/JS/API/分页/详情页/下载链接/登录限制和接入建议。用于判断未知资源站能否由 generic-web-source 直接抽取，或是否值得沉淀独立 source skill；不负责批量下载、资源最终评分或资料库归档。
---

# 网页资源站结构分析

## 目标

接收资源站 URL 或 `learning-resource-source-discovery/v1` 输出，对候选资源站做轻量结构分析，生成 `site-profile/v1`。

本 skill 处于来源发现和候选抽取之间：

```text
resource-source-discovery
  -> web-resource-profiler
  -> generic-web-source 或 独立 source skill
```

本 skill 不做：

- 不批量下载资源。
- 不绕过登录、付费或访问限制。
- 不对具体资源做最终质量评分。
- 不写入最终资料库。

## 输入

可以输入单个 URL：

```bash
python3 skills/web-resource-profiler/scripts/profile_site.py \
  --url https://example.edu.cn/resources
```

也可以输入 `resource-source-discovery` 输出：

```bash
python3 skills/web-resource-profiler/scripts/profile_site.py \
  --discovery-json source-discovery.json
```

离线调试时可传 HTML 文件：

```bash
python3 skills/web-resource-profiler/scripts/profile_site.py \
  --url https://example.edu.cn/resources \
  --html-file sample.html
```

## 输出

输出 `site-profile/v1`，完整契约见 `references/site-profile-schema.md`。

核心字段：

```json
{
  "site_profile_schema": "site-profile/v1",
  "profiles": [
    {
      "source_url": "",
      "site_type": "static_resource_page | resource_listing | spa_app | media_page | article_page | unknown",
      "crawl_strategy": "generic_extract | profile_deeper | dedicated_source_skill | keep_as_web_candidate | reject",
      "resource_links": [],
      "api_hints": [],
      "pagination_hints": [],
      "auth_hints": [],
      "score": 0.0
    }
  ]
}
```

## 结构分析内容

第一版识别：

- 页面标题和 meta 描述。
- PDF/DOC/PPT/图片/音频/视频等直链。
- `script src`、`link href`、前端 chunk。
- 疑似 API 路径和接口域名。
- 搜索框、表单、分页、详情页链接。
- 登录、会员、付费、授权提示。
- SPA 前端应用信号。
- 是否适合通用抽取，还是需要独立 source skill。

## 策略判断

- 直链资源较多：`generic_extract`。
- 列表页、分页、详情页明显：`profile_deeper`。
- SPA + API 信号强：`dedicated_source_skill`。
- 普通文章：`keep_as_web_candidate`。
- 风险或不可访问：`reject`。

## 边界

第一版不会自动下载 JS chunk 深挖，也不会执行浏览器渲染。后续可以增加 Playwright 或 JS 资源抓取，但需要控制成本，只对高价值来源执行。
