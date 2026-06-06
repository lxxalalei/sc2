# 资源站结构分析测试样例

## 样例 1：PDF 列表页

输入 HTML：

- 页面包含多个 `.pdf`、`.docx` 链接。

期望：

- `site_type=static_resource_page` 或 `resource_listing`。
- `crawl_strategy=generic_extract`。
- `resource_links` 不为空。

## 样例 2：SPA 资源站

输入 HTML：

- 有 `div id=root`。
- 有多个 `/js/app-xxx.js`、`chunk-xxx.js`。
- 文本中出现 `/resources/search`、`/content/detail` 等接口。

期望：

- `site_type=spa_app`。
- `crawl_strategy=dedicated_source_skill` 或 `profile_deeper`。
- `api_hints`、`script_hints` 不为空。

## 样例 3：需要登录

输入 HTML：

- 包含“登录后查看”“会员”“付费”等。

期望：

- `auth_hints` 不为空。
- `warnings` 标记可能需要授权。

## 样例 4：普通文章

输入 HTML：

- 没有资源链接、接口、分页。
- 只有普通正文。

期望：

- `site_type=article_page`。
- `crawl_strategy=keep_as_web_candidate`。
