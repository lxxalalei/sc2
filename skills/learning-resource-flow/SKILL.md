---
name: learning-resource-flow
description: 编排学习资源 Agent 的完整调用链。当用户要求查找、搜索、推荐、下载或整理学习资源时优先使用本 skill 作为总入口，例如练习题、课件、音频、视频、图文百科、绘本、教材等请求。本 skill 负责决定是否先追问，并串联 intent、source、analyzer、ranker；不要只停留在单个搜索或下载 skill。
---

# 学习资源工作流编排

## 目标

本 skill 是 OpenClaw 接入时的总控入口，用来把多个学习资源 skills 串成完整流程。来源选择策略见 `references/source-policy.md`。

核心原则：

- 用户提出学习资源需求时，优先进入本 skill。
- 不要只调用某一个来源 skill 后就结束。
- 来源选择保持类型无关、主题无关和格式无关；具体来源作为候选来源参与排序。
- 识别到用户意图后，先解构为结构化任务，再优先查询已经优化好的站点 source skills。
- 已优化来源没有候选、候选太少或质量不足时，再进入通用网络搜索、来源发现和网页结构分析。
- 搜索候选后必须继续进入 `learning-resource-analyzer` 和 `learning-resource-ranker`。
- 除非用户明确确认下载，否则搜索和评分阶段不直接批量下载。

## 当前可用子技能

- `learning-resource-intent`：需求理解、追问、生成 `execution_tasks`。
- `smartedu-resources`：国家中小学智慧教育平台站点级资源入口，统一处理站内教材、课程、课件、习题、试卷、视频、音频、图片等候选。
- `web-learning-search`：通用网页学习资源候选搜索。
- `resource-source-discovery`：从通用搜索结果中识别值得深入分析的资源站候选。
- `web-resource-profiler`：对高价值资源站做结构分析和接入策略判断。
- `generic-web-source`：从简单资源站画像或 HTML 中抽取资源直链候选。
- `learning-resource-analyzer`：候选详情分析。
- `learning-resource-ranker`：候选质量评分排序。
- `learning-resource-selector`：把评分结果整理成用户可选择的清单。
- `learning-resource-downloader`：根据用户选择下载到工作缓存目录。
- `learning-library-organizer`：将已下载文件规范命名、分类并归档到最终资料库。
- `learning-library-index`：在资料库外部维护索引、去重记录和来源追踪。
- `local-library-search`：基于外部索引检索本地已有学习资源候选。

## 标准调用链

流程：

```text
用户请求
  -> learning-resource-intent        # 模型分析、解构、必要时追问
  -> local-library-search           # 若已有外部索引，先检索本地候选
  -> source profiles / site-index   # 读取已优化站点 source 的能力画像和站点索引
  -> optimized source skills        # 先查询已接入、已优化的站点来源
  -> candidate threshold check      # 候选太少或质量不足
  -> agent web search               # 再使用 agent 通用搜索能力获取网络搜索结果
  -> web-learning-search            # 标准化搜索结果候选
  -> resource-source-discovery      # 从搜索结果中发现高价值资源站
  -> web-resource-profiler          # 分析未知资源站结构
  -> generic-web-source             # 简单资源站抽取直链候选
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
  -> 给用户展示排序后的候选
  -> 用户确认后进入 learning-resource-downloader
  -> 下载成功后进入 learning-library-organizer
  -> 归档成功后进入 learning-library-index
```

当前 SmartEdu 站点来源统一由 `smartedu-resources` 承接。后续新增其他站点 source 后，都进入 `source profiles -> optimized source skills` 阶段，不需要改写全局意图逻辑。

SmartEdu 在 flow 中会先加载 `site-index`，把全站 route、扫描策略、tab code 和命令能力作为来源索引，再选择合适的搜索 tab 调用 `search-resources`。可用 `--smartedu-site-index-json` 复用已生成索引，或用 `--smartedu-route-map-json` / `--smartedu-library-list-json` 生成临时索引。

需求已澄清且适合 SmartEdu 时，flow 默认会对 SmartEdu 搜索候选继续执行详情展开，把详情中的视频、PDF、图片、课件、习题等文件项转为 `learning-resource-candidate/v1`，再进入 analyzer/ranker/selector。不要把 SmartEdu 搜索页候选直接当作最终可下载资源；只有详情文件项或经过 downloader 校验的直链才适合下载。

如果用户直接要求下载某个资源，也应先确认候选唯一性；候选唯一、质量高且来源明确时，才进入下载。

## Source-first 执行规则

1. `learning-resource-intent` 先判断是否需要追问；需要追问时立即停止。
2. 需求明确后，先查询本地资料库和已优化站点 source。
3. 已优化 source 的候选必须统一进入 analyzer/ranker，不因为“官方”就直接跳过评分。
4. 若已优化 source 候选少于阈值、质量低、类型不匹配或用户要求更多来源，再让 agent 执行通用网络搜索。
5. 通用搜索结果先交给 `web-learning-search` 标准化，再进入来源发现、站点画像、通用抽取。
6. 所有来源候选合并后统一分析、评分、展示给用户选择。

## 追问规则

如果 `learning-resource-intent` 输出 `status=needs_clarification`，必须先追问用户，不要继续搜索。

常见追问：

- 孩子几岁或几年级？
- 核心学习主题是什么？
- 需要练习题、视频、音频、图片，还是课件？
- 需要打印、自学、亲子共读、课堂使用，还是听赏？
- 如果用户明确要求指定教材、课内同步的唯一资源，或当前来源必须依赖这些字段定位，再追问版本、出版社或册次；普通“想学数学/语文/课程资料”不要默认追问上下册。

## 脚本化通用测试链路

通用 source-first 流程测试：

```bash
python3 skills/learning-resource-flow/scripts/run_resource_flow.py \
  --query "给8岁孩子找四则混合运算练习题，最好能打印" \
  --local-index-file .learning-resource-work/index/resources.json \
  --smartedu-search-response-json skills/smartedu-resources/references/sample-search-response.json \
  --web-search-results-json web-results.json \
  --web-profile-html-file skills/web-resource-profiler/references/sample-resource-page.html \
  --min-source-candidates 3
```

该脚本可以直接接收自然语言 `--query`，并先调用 `learning-resource-intent` 生成结构化 intent；也可以传入已有的 `--intent-json` 用于调试、离线回归或从澄清结果继续执行。

SmartEdu 明确需求到候选清单：

```bash
python3 skills/learning-resource-flow/scripts/run_resource_flow.py \
  --query "我要三年级数学课程的全部资料" \
  --skip-local-search \
  --work-dir .learning-resource-flow-work/smartedu-math \
  -o .learning-resource-flow-work/smartedu-math/selection.json
```

默认会执行：

```text
learning-resource-intent
  -> smartedu-resources search-resources --fetch-details
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

如果详情需要账号态，可加：

```bash
--smartedu-browser-state .smartedu-browser/state.json
```

或使用 `SMARTEDU_ACCESS_TOKEN`、`SMARTEDU_COOKIE`、`SMARTEDU_AUTHORIZATION`、`SMARTEDU_HEADERS` 等环境变量/`.env.local` 授权上下文。

用户确认下载后，在同一条命令追加选择编号：

```bash
--select 1,2 --allow-auth
```

执行链路：

```text
local-library-search
  -> 本地候选数量阈值判断
smartedu-resources site-profile
  -> smartedu-resources site-index
  -> smartedu-resources 候选查询
  -> 候选数量阈值判断
  -> web-learning-search fallback
  -> resource-source-discovery
  -> web-resource-profiler
  -> generic-web-source
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

如果未提供 `--web-search-results-json` 且已优化 source 候选不足，脚本会输出 `needs_web_search=true`，由 agent 使用自身通用搜索能力拿到搜索结果后再继续。

真实运行时通常不传 `--web-profile-html-file`，由 profiler 联网分析来源页面；离线测试时才传本地 HTML fixture。

用户确认下载后，可在同一脚本中继续执行下载、归档和索引更新：

```bash
python3 skills/learning-resource-flow/scripts/run_resource_flow.py \
  --query "给8岁孩子找四则混合运算练习题，最好能打印" \
  --web-search-results-json web-results.json \
  --select 1,2 \
  --library-dir 学习资料库 \
  --index-dir .learning-resource-work/index
```

确认后链路会执行：

```text
learning-resource-downloader
  -> learning-resource-analyzer      # 复查下载后的真实文件
  -> learning-library-organizer
  -> learning-library-index
```

如果只想检查候选是否可访问，不保存文件，可加 `--probe-only`。正式下载后会先复查本地文件，避免把登录页、错误页或格式伪装文件直接当作正常资源归档。最终资料库仍只写入真实资源文件，下载结果、归档摘要和索引更新摘要保存在工作目录或外部索引中。

## 早期兼容链路

以下脚本只用于回归早期 SmartEdu 教材适配能力，不是通用学习资源默认入口。常规请求优先使用上面的 source-first 通用流程。

```bash
python3 skills/learning-resource-flow/scripts/run_textbook_flow.py \
  --stage 小学 \
  --grade 三年级 \
  --subject 数学 \
  --version 人教版 \
  --show 2
```

如果当前项目根目录已有 SmartEdu 索引 `data/textbooks.json`，可避免重新联网同步：

```bash
python3 skills/learning-resource-flow/scripts/run_textbook_flow.py \
  --stage 小学 \
  --grade 三年级 \
  --subject 数学 \
  --version 人教版 \
  --show 2 \
  --smartedu-work-dir .
```

该脚本会执行：

```text
smartedu-resources 内部教材候选能力
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

输出 `learning-resource-selection/v1` 可选清单。

## 回复规则

给用户回复时，应包含：

1. 是否已完成候选搜索。
2. selector 生成的候选编号。
3. 每个推荐候选的标题、来源、评分、格式、是否需要登录授权。
4. 是否需要用户确认下载。

不要把 JSON 缓存、临时工作目录、manifest 或 token 展示为最终资料库内容。

下载后的归档结果应只把真实资源文件写入最终资料库；归档摘要、索引和调试 JSON 留在工作目录或外部索引中。

索引更新必须使用资料库外部目录，例如 `.learning-resource-work/index/`；不要在最终资料库中写入索引文件。

如果存在本地索引，搜索外部来源前应优先调用 `local-library-search` 生成本地候选；本地候选仍需进入 analyzer、ranker、selector，不要绕过统一评分和用户选择。

通用搜索结果较多时，应先用 `resource-source-discovery` 做来源级粗筛。它只判断“哪个站值得深入分析”，不替代资源级 analyzer/ranker。

`web-resource-profiler` 只分析 discovery 选出的高价值来源，用于判断是否可用通用网页抽取、是否需要独立 source skill，或是否应放弃。

当 `web-resource-profiler` 输出 `crawl_strategy=generic_extract` 且存在 `resource_links` 时，调用 `generic-web-source` 将资源直链转换为标准候选；当输出 `dedicated_source_skill`、`profile_deeper` 或 `reject` 时，不要强行通用抽取。
