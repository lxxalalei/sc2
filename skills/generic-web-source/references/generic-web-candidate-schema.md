# 通用网页资源候选输出

`generic-web-source` 输出 `learning-resource-candidate/v1`。

## 顶层结构

```json
{
  "candidate_schema": "learning-resource-candidate/v1",
  "source_skill": "generic-web-source",
  "query": "",
  "filters": {},
  "searched_at": "",
  "candidates": [],
  "summary": {
    "profiles": 0,
    "links_seen": 0,
    "candidates": 0,
    "skipped": 0
  }
}
```

## 候选字段补充

```json
{
  "source": "generic-web-source",
  "source_name": "example.edu.cn",
  "source_url": "https://example.edu.cn/files/demo.pdf",
  "resource_id": "",
  "title": "三年级数学练习题 PDF",
  "description": "来自 小学三年级数学练习题资源",
  "resource_type": "习题",
  "format": "pdf",
  "downloadable": true,
  "requires_auth": false,
  "raw": {
    "origin_page_url": "https://example.edu.cn/resources",
    "origin_title": "小学三年级数学练习题资源",
    "direct_url": "https://example.edu.cn/files/demo.pdf",
    "extraction_method": "site-profile",
    "warnings": []
  }
}
```

## 字段原则

- `source_url` 是具体资源直链，不是来源页面。
- `raw.origin_page_url` 保留资源站页面地址。
- `downloadable=true` 只表示链接看起来是文件直链，不代表已经下载成功。
- `requires_auth` 只在画像或链接文本出现登录、会员、付费、授权等信号时为 `true`。
- 不要把用户 filters 直接复制成候选学科/主题，除非标题、链接文本或 URL 中出现对应证据。
