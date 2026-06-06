# SmartEdu 通用资源输出契约

## 候选输出

`smartedu-resources` 输出 `learning-resource-candidate/v1`。

```json
{
  "candidate_schema": "learning-resource-candidate/v1",
  "source_skill": "smartedu-resources",
  "query": "",
  "filters": {},
  "candidates": [],
  "summary": {
    "details": 0,
    "items_seen": 0,
    "candidates": 0,
    "skipped": 0
  }
}
```

候选中的 `raw.smartedu_item` 保留原始 `ti_items` 文件项。`source_url` 优先使用可识别的文件或播放地址；如果只有私有 NDR 地址，`requires_auth=true`。

站内搜索候选中的 `raw.smartedu_search_item` 保留搜索结果原始项。此类候选通常只有详情页或元数据，因此：

```json
{
  "downloadable": false,
  "raw": {
    "warnings": ["搜索结果候选尚未解析详情文件项"]
  }
}
```

后续应继续抓取详情 JSON，并用 `candidates-from-detail` 解析为可下载或可播放的文件项候选。

当使用 `search-resources --fetch-details` 时，输出仍为 `learning-resource-candidate/v1`，但候选会优先来自详情 `ti_items`：

```json
{
  "summary": {
    "fetch_details": true,
    "details_fetched": 1,
    "detail_items_seen": 3,
    "detail_failures": 0
  },
  "candidates": [
    {
      "downloadable": true,
      "raw": {
        "smartedu_item": {},
        "url_candidates": []
      }
    }
  ]
}
```

如果某个搜索项无法获取详情，应保留搜索候选并在 `detail_failures` 中记录失败原因。

## 授权上下文

联网命令可以从运行环境读取授权信息：

```text
SMARTEDU_ACCESS_TOKEN
SMARTEDU_COOKIE
SMARTEDU_AUTHORIZATION
SMARTEDU_HEADERS
```

也可以使用命令行参数：

```text
--access-token
--cookie
--header "Name: value"
```

输出中只允许出现：

```json
{
  "summary": {
    "auth_context": true
  }
}
```

不得把 token、cookie、authorization 或自定义 header 的原文写入候选、日志、资料库、索引或计划文档。

## 栏目画像输出

```json
{
  "catalog_profile_schema": "smartedu-catalog-profile/v1",
  "source_skill": "smartedu-resources",
  "catalogs": [],
  "summary": {
    "catalogs": 0,
    "resource_catalogs": 0,
    "external_catalogs": 0
  }
}
```

教材候选仍使用 `learning-resource-candidate/v1`，对外来源保持：

```json
{
  "source_skill": "smartedu-resources",
  "resource_family": "教材",
  "internal_adapter": "tchMaterial",
  "candidates": [
    {
      "source": "smartedu-resources",
      "resource_type": "教材",
      "format": "pdf",
      "raw": {
        "internal_adapter": "tchMaterial",
        "smartedu_catalog": "tchMaterial"
      }
    }
  ]
}
```

这表示教材是 SmartEdu 站内资源分支，不是外部独立资源站来源。

## 资源类型映射

- `m3u8`、`mp4`、`video/*` -> `视频`
- `mp3`、`wav`、`m4a`、`audio/*` -> `音频`
- `pdf` -> `文档`
- `ppt`、`pptx` -> `课件`
- `doc`、`docx`、`txt` -> `文档`
- `jpg`、`png`、`webp`、`image/*` -> `图片`
- `zip`、`rar`、`7z` -> `压缩包`

## 访问限制

如果 `custom_properties.identification=true`，或 URL 位于 `r*-ndr-private.ykt.cbern.com.cn`，候选应标记：

```json
{
  "requires_auth": true,
  "raw": {
    "warnings": ["可能需要 SmartEdu 登录授权"]
  }
}
```
