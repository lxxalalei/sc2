---
name: resource-source-discovery
description: 从 agent 搜索结果或 web-learning-search 候选中识别潜在学习资源站，做来源级粗筛、风险标记和是否值得深入分析的判断。用于大量网络搜索后，在 web-resource-profiler 或具体 source skill 之前筛选资源站；不负责下载、深度爬取、资源评分或资料库归档。
---

# 资源站发现与粗筛

## 目标

接收搜索结果或网页候选，识别哪些 URL 像学习资源站、资源详情页、普通文章、视频页、下载风险页，并给出来源级评分和下一步建议。

本 skill 位于搜索和深度分析之间：

```text
agent 通用搜索 / web-learning-search
  -> resource-source-discovery
  -> web-resource-profiler 或具体 source skill
```

本 skill 不做：

- 不下载文件。
- 不抓取深层页面。
- 不评分具体资源质量。
- 不写入最终资料库。
- 不把来源类型和资源类型硬绑定。

## 输入

优先接收 `learning-resource-candidate/v1`：

```json
{
  "candidate_schema": "learning-resource-candidate/v1",
  "query": "",
  "filters": {},
  "candidates": []
}
```

也可以接收 agent 搜索结果：

```json
{
  "query": "8岁 四则混合运算 练习题 PDF",
  "search_results": [
    {
      "title": "",
      "url": "",
      "snippet": ""
    }
  ]
}
```

## 输出

输出 `learning-resource-source-discovery/v1`，完整契约见 `references/source-discovery-schema.md`。

```json
{
  "source_discovery_schema": "learning-resource-source-discovery/v1",
  "query": "",
  "sources": [],
  "rejected_sources": []
}
```

## 来源类型

第一版识别：

- `known_source`：已知可交给专用 source skill 的站点。
- `resource_site`：疑似学习资源站、资源列表页或资料库。
- `resource_page`：疑似单个资源详情页或文件页。
- `video_page`：视频平台或播放页。
- `article_page`：普通文章、介绍页、百科页。
- `download_risk`：疑似下载器、破解、广告或高风险下载页。
- `unknown`：无法判断。

## 下一步建议

`next_action` 取值：

- `use_known_source_skill`：交给已知 source skill。
- `profile_site`：交给后续 `web-resource-profiler` 深入分析。
- `extract_direct_candidates`：交给通用网页资源抽取器。
- `keep_as_web_candidate`：保留为普通网页候选，后续资源评分决定。
- `reject`：不建议继续。

## 使用脚本

从 `web-learning-search` 候选读取：

```bash
python3 skills/resource-source-discovery/scripts/discover_sources.py \
  web-candidates.json
```

从 agent 搜索结果读取：


```bash
python3 skills/resource-source-discovery/scripts/discover_sources.py \
  search-results.json
```

输出到文件：

```bash
python3 skills/resource-source-discovery/scripts/discover_sources.py \
  web-candidates.json \
  -o .learning-resource-work/source-discovery.json
```

## 使用边界

- 该 skill 是粗筛，不替代 profiler。
- 分数高表示“值得进一步分析”，不表示具体资源质量高。
- 对已知来源只给出路由建议，不直接调用对应 source skill。
- 风险站点应进入 `rejected_sources`，除非用户明确要求审查风险来源。
