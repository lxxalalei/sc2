# 资源站发现测试样例

## 样例 1：已知官方来源

输入：

- URL 包含 `basic.smartedu.cn/tchMaterial`。

期望：

- `source_type=known_source`。
- `known_skill=smartedu-resources`。
- `next_action=use_known_source_skill`。

## 样例 2：资源密集页

输入：

- 标题或摘要包含“课件、PPT、PDF、练习题、试卷、下载”等。
- URL 看起来不是直接文件。

期望：

- `source_type=resource_site` 或 `resource_page`。
- `next_action=profile_site`。

## 样例 3：PDF 直链

输入：

- URL 以 `.pdf` 结尾。

期望：

- `source_type=resource_page`。
- `next_action=extract_direct_candidates`。
- `resource_format_hints` 包含 `pdf`。

## 样例 4：风险下载页

输入：

- 标题或摘要包含“高速下载器、破解、成人、博彩”等。

期望：

- 进入 `rejected_sources`。
- `next_action=reject`。

## 样例 5：普通文章

输入：

- 标题为“如何培养孩子阅读兴趣”，没有明显可下载资源信号。

期望：

- `source_type=article_page`。
- `next_action=keep_as_web_candidate`。
