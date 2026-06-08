---
name: smartedu-resources
description: 国家中小学智慧教育平台 / SmartEdu 站点级资源 skill，用于统一识别和处理站内教材、课程、课件、习题、试卷、视频、音频、图片、实验、专题、家庭教育、德育、课后服务等学习资源候选；可解析 SmartEdu 栏目清单、站内搜索结果和详情 JSON 的 ti_items 为 learning-resource-candidate/v1。教材 tchMaterial 是本 skill 的站内资源类型之一，不作为独立来源暴露。
---

# SmartEdu 通用资源来源

## 目标

本 skill 是 SmartEdu 站点级通用资源工具。它应该对 `basic.smartedu.cn` 站内资源有统一掌控能力：教材、课程教学视频、备课资料、PPT、习题、试卷、实验、家庭教育、专题资源等都属于同一个 SmartEdu source。

教材 `tchMaterial` 只是 SmartEdu 站内资源类型之一。早期跑通的教材脚本可以作为内部适配能力复用，但外部任务路由、来源发现和 OpenClaw 调用都应优先进入 `smartedu-resources`，不要把“教材”独立成另一个站点来源。

当前第一版重点：

- 输出站点能力画像，说明本 source 能处理哪些资源、哪些命令可用、哪些能力需要运行态授权或接口联调。
- 读取 SmartEdu 栏目清单，输出资源栏目画像。
- 输出栏目路由图，说明栏目页、搜索 tab、详情模板和内部适配策略。
- 按栏目路由扫描资源候选，支持离线搜索响应归一化和在线接口联调。
- 按 route-map 批量扫描多个栏目，输出站点级候选索引摘要。
- 从 SmartEdu 页面 HTML/JS 中提取接口、详情 ID、资源链接和下一步动作线索。
- 调用或归一化 SmartEdu 站内资源搜索结果，输出候选资源。
- 输出 SmartEdu 站内教材候选，内部复用早期 `tchMaterial` 教材适配资产。
- 解析 SmartEdu 详情 JSON 中的 `ti_items`。
- 将视频、音频、PDF、图片、文档、课件、压缩包等文件项转为 `learning-resource-candidate/v1`。
- 将 `tchMaterial` 标记为站内教材资源分支，保留 `internal_adapter=tchMaterial`，但 `known_skill` 仍为 `smartedu-resources`。
- 保留 `raw.smartedu_item`，供后续专门下载团队处理 token、cookie、m3u8、私有 NDR 链接和批量下载。

## 使用边界

- 不批量下载资源。
- 不写最终资料库。
- 不把 token、cookie 或 authorization header 写入文件、文档、代码默认值或日志。
- 不绕过登录、授权或付费限制。
- 不替代 analyzer/ranker/selector。

## 常用命令

输出 SmartEdu 站点能力画像：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  site-profile \
  --library-list-json skills/smartedu-resources/references/sample-librarylist.json
```

列出 SmartEdu 栏目画像：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  list-catalogs \
  --library-list-json skills/smartedu-resources/references/sample-librarylist.json
```

输出 SmartEdu 栏目路由图：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  route-map \
  --library-list-json skills/smartedu-resources/references/sample-librarylist.json
```

分析 SmartEdu 页面结构线索：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  page-profile \
  --url https://basic.smartedu.cn/ \
  --html-file skills/smartedu-resources/references/sample-page.html
```

按栏目路由扫描候选：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  scan-catalog \
  --route-map-json smartedu-route-map.json \
  --type qualityCourse \
  --query "三年级数学"
```

批量扫描多个栏目：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  scan-site \
  --route-map-json smartedu-route-map.json \
  --catalog syncClassroom \
  --route-limit 3 \
  --query "三年级数学"
```

离线调试时可以传入已有搜索响应：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  scan-catalog \
  --route-map-json smartedu-route-map.json \
  --type qualityCourse \
  --search-response-json skills/smartedu-resources/references/sample-search-response.json
```

搜索 SmartEdu 资源候选：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  search-resources \
  --query "三年级数学分数" \
  --tab-code qualityCourse \
  -o smartedu-search-candidates.json
```

搜索后继续追踪详情并解析文件项：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  search-resources \
  --query "三年级数学分数" \
  --tab-code qualityCourse \
  --fetch-details \
  -o smartedu-file-candidates.json
```

归一化已有搜索响应：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  search-resources \
  --query "三年级数学" \
  --search-response-json skills/smartedu-resources/references/sample-search-response.json
```

列出 SmartEdu 站内教材候选：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  textbook-candidates \
  --stage 小学 \
  --grade 三年级 \
  --subject 数学 \
  --version 人教版
```

解析详情 JSON 为候选资源：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  candidates-from-detail \
  --detail-json detail.json \
  -o smartedu-resource-candidates.json
```

根据资源 ID 和栏目尝试抓取详情：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  candidates-from-detail \
  --catalog qualityCourse \
  --resource-id RESOURCE_ID
```

带账号态调用时，通过运行环境注入凭据，不要写进 skill 文件：

```bash
SMARTEDU_ACCESS_TOKEN='...' \
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  search-resources \
  --query "三年级数学"
```

可选环境变量：

```text
SMARTEDU_ACCESS_TOKEN
SMARTEDU_COOKIE
SMARTEDU_AUTHORIZATION
SMARTEDU_HEADERS
```

也可临时传入 `--cookie` 或 `--header 'Name: value'`。脚本输出只会记录 `auth_context=true/false`，不会输出凭据原文。

## 调用位置

在总流程中，`smartedu-resources` 是普通 source skill：

```text
learning-resource-intent
  -> smartedu-resources
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

如果来源发现阶段识别出 `basic.smartedu.cn`，交给本 skill 判断栏目和资源类型。无论用户要教材、课程视频、PPT、习题还是家庭教育资源，都先作为 SmartEdu 站内候选处理；只有在内部实现层需要复用早期教材下载脚本时，才使用 `internal_adapter=tchMaterial`。

站内搜索候选不等同于最终下载地址。搜索阶段通常只得到详情页或资源元数据；下载前应继续抓取详情 JSON，解析 `ti_items` 后再交给下载 skill 或后续专门下载团队处理。

如果调用 `search-resources --fetch-details`，本 skill 会尝试把搜索结果继续追踪到详情 JSON，并将详情中的 `ti_items` 展开为真实文件项候选。详情获取失败的搜索结果会保留为普通候选，并在 `detail_failures` 中记录失败原因。

真实环境联调建议分两步：

```bash
SMARTEDU_ACCESS_TOKEN='...' \
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  search-resources \
  --query "三年级数学分数" \
  --fetch-details \
  -o /tmp/smartedu-file-candidates.json
```

然后将候选经过 selector 转为选择清单，再用 downloader 先探测：

```bash
SMARTEDU_ACCESS_TOKEN='...' \
python3 skills/learning-resource-downloader/scripts/download_selected.py \
  selection.json \
  --select A \
  --allow-auth \
  --probe-only
```

## 输出

站点能力画像输出契约：

```text
learning-resource-source-profile/v1
```

候选输出契约：

```text
learning-resource-candidate/v1
```

栏目画像输出契约：

```text
smartedu-catalog-profile/v1
```

栏目路由图输出契约：

```text
smartedu-route-map/v1
```

页面画像输出契约：

```text
smartedu-page-profile/v1
```

栏目扫描输出契约：

```text
smartedu-catalog-scan/v1
```

站点扫描输出契约：

```text
smartedu-site-scan/v1
```
