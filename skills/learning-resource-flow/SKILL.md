---
name: learning-resource-flow
description: 编排学习资源 Agent 的完整调用链。当用户要求查找、搜索、推荐、下载或整理学习资源时优先使用本 skill 作为总入口，尤其是“帮我找教材”“查找小学三年级数学教材”“下载人教版小学三年级数学上册”“找四则运算练习题”等请求。本 skill 负责决定是否先追问，并串联 intent、source、analyzer、ranker；不要只停留在单个搜索或下载 skill。
---

# 学习资源工作流编排

## 目标

本 skill 是 OpenClaw 接入时的总控入口，用来把多个学习资源 skills 串成完整流程。来源选择策略见 `references/source-policy.md`。

核心原则：

- 用户提出学习资源需求时，优先进入本 skill。
- 不要只调用某一个来源 skill 后就结束。
- 来源选择保持类型无关、主题无关和格式无关；具体来源作为候选来源参与排序。
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

### 教材类请求

适用：

- 查找教材
- 搜索课本
- 电子教材
- 人教版/统编版/北师大版等版本教材

流程：

```text
用户请求
  -> learning-resource-intent
  -> local-library-search           # 若已有外部索引，先检索本地候选
  -> source skills 候选搜索         # SmartEdu 站点统一走 smartedu-resources
  -> resource-source-discovery      # 对通用搜索结果做来源级粗筛
  -> web-resource-profiler          # 对高价值未知资源站做结构分析
  -> generic-web-source             # 对 profiler 判定可通用抽取的来源生成候选
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
  -> 给用户展示排序后的候选
  -> 用户确认后进入 learning-resource-downloader
  -> 下载成功后进入 learning-library-organizer
  -> 归档成功后进入 learning-library-index
```

当前 SmartEdu 站点来源统一由 `smartedu-resources` 承接。早期教材脚本只作为该站点内部适配能力保留，不应作为外部独立来源参与路由。后续新增其他资源站后，应和 `smartedu-resources` 一起进入候选和评分。

如果用户直接说“下载人教版小学三年级数学上册”，也应先确认候选唯一性；候选唯一、质量高且来源明确时，才进入下载。

### 主题学习类请求

适用：

- 四则运算练习题
- 恐龙百科视频
- 唐诗宋词启蒙音频
- 儿歌、绘本、识字、科学启蒙等

流程：

```text
用户请求
  -> learning-resource-intent
  -> local-library-search           # 若已有外部索引，先检索本地候选
  -> smartedu-resources             # 若需求适合 SmartEdu 官方平台资源
  -> web-learning-search
  -> resource-source-discovery      # 找出值得 profiler 深挖的资源站
  -> web-resource-profiler
  -> generic-web-source             # 对简单资源站抽取资源直链候选
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
  -> 给用户展示排序后的候选
  -> 用户确认后进入 learning-resource-downloader
  -> 下载成功后进入 learning-library-organizer
  -> 归档成功后进入 learning-library-index
```

## 追问规则

如果 `learning-resource-intent` 输出 `status=needs_clarification`，必须先追问用户，不要继续搜索。

教材类常见追问：

- 需要哪个学段和年级？
- 需要哪个学科？
- 需要哪个版本或出版社？
- 需要上册、下册，还是先列出候选？

主题类常见追问：

- 孩子几岁或几年级？
- 核心学习主题是什么？
- 需要练习题、视频、音频、图片，还是课件？

## 脚本化教材测试链路

为了在 OpenClaw 中测试当前已实现的官方教材来源链路，可使用：

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
