# 测试用例

## 用例 1：站点能力画像

输入 `sample-librarylist.json`。

期望：

- 输出 `learning-resource-source-profile/v1`。
- 说明本来源是普通候选来源，不与主题、类型或格式硬绑定。
- 能列出站内资源类型、格式覆盖、可用命令和授权策略。
- 如果传入 header、cookie 或 token，只能输出 `auth_context=true`，不得泄露原文。

## 用例 2：栏目画像

输入 `sample-librarylist.json`。

期望：

- 输出 `smartedu-catalog-profile/v1`。
- 能识别课程教学、备课资源、精品课、实验教学、家庭教育。
- 教材栏目应仍标记为 `known_skill=smartedu-resources`，并通过 `resource_family=教材`、`internal_adapter=tchMaterial` 表示站内教材资源分支。

## 用例 3：详情资源项解析

输入 `sample-detail.json`。

期望：

- 输出 `learning-resource-candidate/v1`。
- 生成视频、PDF、图片候选。
- `custom_properties.identification=true` 的候选标记 `requires_auth=true`。
- 候选保留 `raw.smartedu_item`。

## 用例 4：与 analyzer/ranker 串联

`candidates-from-detail` 输出应能直接交给 `learning-resource-analyzer` 和 `learning-resource-ranker`。

## 用例 5：不下载

脚本不应下载 m3u8、PDF、图片或其他真实文件；只输出候选和元数据。

## 用例 6：全站索引

输入 `route-map` 输出 JSON。

期望：

- 输出 `smartedu-site-index/v1`。
- 默认索引全部 route，而不是只取前几条。
- `coverage.scan_strategies` 同时包含 `search_then_detail` 和内部适配策略。
- `scan_plan` 为每条 route 保留 route_id、栏目、扫描策略、tab code 和可用命令。
- 如果传入 `scan-site` JSON，应合并候选、失败和扫描摘要，但不下载任何资源。

## 用例 7：新版公开搜索端点

输入关键词 `数学五年级`。

期望：

- 优先请求 `https://x-search.ykt.eduyun.cn/v1/resources/combine/search`。
- 请求头包含 `sdp-app-id`、`Origin`、`Referer` 和浏览器 `User-Agent`。
- 不要求把 `Authorization: MAC ...` 写入脚本或配置。
- 输出搜索候选时清理标题中的 HTML 高亮标签，并从 tags/extra 中提取年级、学科、版本、册次、格式和 provider。

## 用例 8：详情探测

输入 `sample-search-response.json` 和本地详情目录。

期望：

- 输出 `smartedu-detail-probe/v1`。
- 每个搜索候选输出 `resource_id`、`catalog`、`detail_page`、详情 URL 尝试、`detail_status` 和 `detail_access_policy`。
- 命中本地详情 JSON 时，能统计 `ti_items` 数量和解析出的候选数量。
- 离线模式缺少详情 JSON 时，标记 `detail_not_found_in_dir`，但不丢弃其他候选探测结果。
- 如果传入 header、cookie 或 token，只能输出 `auth_context=true`，不得泄露原文。

## 用例 9：浏览器会话脱敏摘要

输入 Playwright storage state。

期望：

- `export-context` 输出 `smartedu-browser-session/v1`。
- 只记录 `auth_context`、cookie 数量、cookie 域名、localStorage origin 和能力标签。
- 不输出 cookie value、localStorage value、Authorization、MAC 或 `x-nd-auth`。
- `check --offline` 只检查本地 state 摘要，不发起网络请求。
- 真实 `login/check/request` 依赖可选 Playwright，不进入默认离线回归。
