# 学习资源 Agent Toolkit

本项目目标是构建一套面向 3-12 岁儿童与家长的学习资源需求 agent 工作流：从用户自然语言需求出发，完成需求澄清、多来源搜索、资源质量评分、用户选择、下载到本地、文件识别归档，并最终形成结构化学习资料库。

学习主题不限定为课内教材或教辅，也包括四则运算、拼音识字、儿童百科、唐诗宋词、儿歌、绘本、科学启蒙、艺术启蒙、逻辑思维等。项目当前从国家中小学智慧教育平台官方教材开始探索，逐步扩展到课件、习题、试卷、图片、音频、视频、网页资料等多格式学习资源。

## 项目入口

继续开发前先阅读：

- [PROJECT.md](PROJECT.md)：项目入口与工作约束
- [docs/learning-resource-agent-plan.md](docs/learning-resource-agent-plan.md)：主计划、进度、架构和后续任务

每次推进 skill、脚本、接口契约或资料库规则后，都需要更新进度文档。

## 总体流程

```text
用户需求
  -> 需求理解与澄清
  -> 多来源搜索
  -> 资源质量评分
  -> 用户选择
  -> 下载到本地
  -> 文件识别、命名与归档
  -> 外部索引与去重
  -> 结构化学习资料库
```

## 当前 Skills

### `learning-resource-flow`

位置：[skills/learning-resource-flow](skills/learning-resource-flow)

OpenClaw 接入时建议优先加载并触发的总控入口。负责把用户学习资源需求串联到后续 skills，避免只调用搜索或下载后就结束。

教材测试链路：

```bash
python3 skills/learning-resource-flow/scripts/run_textbook_flow.py \
  --stage 小学 --grade 三年级 --subject 数学 --version 人教版 \
  --show 2 --smartedu-work-dir .
```

该命令只用于当前 SmartEdu 测试源，会执行：

```text
smartedu-resources 内部教材候选能力 -> learning-resource-analyzer -> learning-resource-ranker
  -> learning-resource-selector
```

### `learning-resource-intent`

位置：[skills/learning-resource-intent](skills/learning-resource-intent)

负责在搜索前理解和澄清用户需求，输出结构化意图。它不搜索、不下载、不归档，只判断用户需求是否足够明确，并生成搜索计划。当前采用“主题优先”模型，优先分析孩子年龄/阶段、核心学习主题、学习目标和资源形式；只有用户明确请求教材或课内同步资料时，才把版本和册次作为关键槽位。

示例能力：

- “我要四则整数运算的学习资料” -> 追问孩子年龄/年级、学习目标和资源形式。
- “找点儿童百科” -> 追问年龄、百科主题和图文/视频/音频偏好。
- “给 5 岁孩子找唐诗宋词启蒙音频” -> 生成主题资源搜索计划。
- “先看看小学三年级数学教材有哪些” -> 生成多来源教材候选查询计划。
- “下载人教版小学三年级数学上册” -> 先生成候选并评分，用户确认后下载。

### `smartedu-resources`

位置：[skills/smartedu-resources](skills/smartedu-resources)

负责统一分析国家中小学智慧教育平台站内资源，例如教材、课程教学、备课资源、精品课、习题、试卷、实验教学、德育、家庭教育、课后服务、专题、图片、音频、视频等。教材 `tchMaterial` 是 SmartEdu 站内资源类型之一，外部路由仍进入本 skill；早期教材脚本只作为内部兼容调试资产保留。第一版只输出标准候选，不批量下载、不写资料库。

早期教材脚本说明见：[docs/smartedu-textbooks-usage.md](docs/smartedu-textbooks-usage.md)

候选输出契约：

```text
learning-resource-candidate/v1
```

栏目画像：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  list-catalogs \
  --library-list-json skills/smartedu-resources/references/sample-librarylist.json
```

详情解析：

```bash
python3 skills/smartedu-resources/scripts/smartedu_resources.py \
  candidates-from-detail \
  --detail-json skills/smartedu-resources/references/sample-detail.json
```

### `learning-resource-ranker`

位置：[skills/learning-resource-ranker](skills/learning-resource-ranker)

负责对 source skill 返回的候选学习资源进行质量评分、排序和风险解释。它不搜索、不下载，只根据用户需求、`ranking_profile` 和候选资源元数据判断哪些资源更值得展示给用户。

评分输出契约：

```text
learning-resource-ranking/v1
```

脚本调用：

```bash
python3 skills/learning-resource-ranker/scripts/rank_candidates.py input.json
```

### `learning-resource-selector`

位置：[skills/learning-resource-selector](skills/learning-resource-selector)

负责把评分后的候选资源整理为用户可选择的清单，生成 A/B/C 编号、摘要、风险提示和下一步动作。它不下载，只等待用户确认。

输出契约：

```text
learning-resource-selection/v1
```

### `learning-resource-downloader`

位置：[skills/learning-resource-downloader](skills/learning-resource-downloader)

负责根据用户在候选清单中的选择下载资源到工作缓存目录。它不写入最终资料库，不做分类归档；后续由 organizer 处理入库。

输出契约：

```text
learning-resource-download/v1
```

### `learning-library-organizer`

位置：[skills/learning-library-organizer](skills/learning-library-organizer)

负责将已下载资源从工作缓存整理到最终学习资料库，完成安全命名、分类路径生成、低置信度 `待确认/` 归档。它不搜索、不评分、不下载；最终资料库内只写入真实资源文件，归档 JSON 应保存在工作目录或外部索引中。

输出契约：

```text
learning-library-organize/v1
```

脚本调用：

```bash
python3 skills/learning-library-organizer/scripts/organize_downloads.py \
  download-result.json --library-dir 学习资料库 \
  -o .learning-resource-work/organize-result.json
```

### `learning-library-index`

位置：[skills/learning-library-index](skills/learning-library-index)

负责在最终资料库外部维护资源索引、去重记录和来源追踪。它不搜索、不评分、不下载、不移动资料库文件；索引文件默认放在 `.learning-resource-work/index/`，不得写入最终资料库。

输出契约：

```text
learning-library-index-update/v1
```

脚本调用：

```bash
python3 skills/learning-library-index/scripts/update_index.py \
  organize-result.json --index-dir .learning-resource-work/index \
  --library-dir 学习资料库 \
  -o .learning-resource-work/index/index-update-result.json
```

### `web-learning-search`

位置：[skills/web-learning-search](skills/web-learning-search)

负责根据 `learning-resource-intent` 生成的 `execution_tasks` 搜索通用网页学习资源候选，适用于四则运算练习、儿童百科、唐诗宋词、儿歌、绘本、课件、图片、音频、视频和网页资料等非固定来源需求。它只输出候选，不评分、不下载。

候选输出契约：

```text
learning-resource-candidate/v1
```

脚本调用：

```bash
python3 skills/web-learning-search/scripts/search_web_resources.py \
  --task-json skills/web-learning-search/references/sample-task.json \
  --limit 10
```

### `resource-source-discovery`

位置：[skills/resource-source-discovery](skills/resource-source-discovery)

负责从 agent 搜索结果或 `web-learning-search` 候选中识别潜在资源站，做来源级粗筛、风险标记和是否值得深入分析的判断。它不下载、不深度爬取、不替代资源评分；后续可把高价值来源交给 `web-resource-profiler` 或具体 source skill。

输出契约：

```text
learning-resource-source-discovery/v1
```

脚本调用：

```bash
python3 skills/resource-source-discovery/scripts/discover_sources.py \
  skills/resource-source-discovery/references/sample-web-candidates.json
```

### `web-resource-profiler`

位置：[skills/web-resource-profiler](skills/web-resource-profiler)

负责对 `resource-source-discovery` 选出的高价值资源站做结构分析，识别 HTML、资源直链、脚本、疑似 API、分页、详情页、登录限制，并给出接入策略。它不批量下载、不做资源最终评分、不写资料库。

输出契约：

```text
site-profile/v1
```

脚本调用：

```bash
python3 skills/web-resource-profiler/scripts/profile_site.py \
  --url https://example.edu.cn/resources \
  --html-file skills/web-resource-profiler/references/sample-resource-page.html
```

### `generic-web-source`

位置：[skills/generic-web-source](skills/generic-web-source)

负责对 `web-resource-profiler` 判定为 `generic_extract` 的简单资源站抽取资源直链候选，例如 PDF、DOCX、PPTX、图片、音频、视频和压缩包。它不下载、不评分、不写资料库；候选仍进入 analyzer、ranker、selector。

输出契约：

```text
learning-resource-candidate/v1
```

脚本调用：

```bash
python3 skills/generic-web-source/scripts/extract_candidates.py \
  --site-profile-json site-profile.json \
  -o generic-candidates.json
```

### `local-library-search`

位置：[skills/local-library-search](skills/local-library-search)

负责基于 `.learning-resource-work/index/resources.json` 检索本地已归档学习资料，并输出标准候选。它是 source skill，只返回候选，不评分、不下载、不修改资料库；本地候选仍需进入 analyzer、ranker、selector。

输出契约：

```text
learning-resource-candidate/v1
```

脚本调用：

```bash
python3 skills/local-library-search/scripts/search_local_library.py \
  --query "四则混合运算 练习题" \
  --index-file .learning-resource-work/index/resources.json
```

### `learning-resource-analyzer`

位置：[skills/learning-resource-analyzer](skills/learning-resource-analyzer)

负责对候选资源做格式识别、详情解析和内容证据提取，位于搜索和评分之间。第一版支持本地 HTML/TXT/PDF/DOCX/PPTX 的轻量分析，支持图片宽高提取，并为音频、视频保留元数据分析入口。

分析输出契约：

```text
learning-resource-analysis/v1
```

脚本调用：

```bash
python3 skills/learning-resource-analyzer/scripts/analyze_candidates.py \
  skills/learning-resource-analyzer/references/sample-candidates.json
```

## 资料库原则

最终资料库目录只放学习资源文件，例如 PDF、DOCX、PPTX、图片、视频等。

以下内容不得放入最终资料库：

- 索引 JSON
- manifest
- 日志
- 临时下载文件
- token 或 cookie
- 爬虫缓存

建议资料库结构：

```text
学习资料库/
  学段/
    年级/
      学科/
        版本或来源/
          册次或主题/
            资源类型/
              文件
  待确认/
```

## 工作缓存

爬虫索引、详情 JSON、下载 manifest、质量评分结果、分类证据等应放入工作目录或外部索引中，不进入最终资料库。

当前 `.gitignore` 已排除：

- `data/`
- `downloads/`
- `.smartedu-textbooks-work/`
- `教材资料库/`
- `学习资料库/`

## 回归验证

当前提供一个离线 smoke test，用于打包或接入 OpenClaw 前快速验证主要契约：

```bash
python3 scripts/run_smoke_tests.py
```

该脚本不联网，会在 `/tmp/learning-resource-skill-smoke` 下构造临时资源，验证：

- 网页搜索结果标准化。
- analyzer/ranker/selector 链路。
- DOCX、PPTX、PNG、HTML 风险页等多格式 analyzer 样例。
- SmartEdu 全平台栏目画像和详情资源项解析。
- source discovery、资源站结构分析和通用网页资源抽取。
- 下载结果归档到最终资料库。
- 外部索引创建和资料库内部写入保护。
- 基于索引的本地资料库检索。

## 设计约束

- 所有 skill 的 `SKILL.md`、示例、面向 agent 的说明和 UI 元数据以中文为基本语言。
- 脚本内部可以保留必要英文命令参数和 JSON 字段名，便于程序对接。
- 每个来源站点或资源类型优先拆成独立 source skill。
- 来源 skill 只负责搜索和返回候选，不负责全局评分。
- 评分、选择、下载、归档应拆成独立 skill 逐步实现。

## 当前状态

已完成：

- SmartEdu 官方教材爬虫。
- `smartedu-textbooks` 第一版。
- `smartedu-resources` 第一版。
- `learning-resource-intent` 第一版。
- `learning-resource-flow` 第一版。
- `learning-resource-ranker` 第一版。
- `learning-resource-selector` 第一版。
- `learning-resource-downloader` 第一版。
- `learning-library-organizer` 第一版。
- `learning-library-index` 第一版。
- `local-library-search` 第一版。
- `resource-source-discovery` 第一版。
- `web-resource-profiler` 第一版。
- `generic-web-source` 第一版。
- `web-learning-search` 第一版。
- `learning-resource-analyzer` 第一版。
- 标准候选资源契约初版。
- 离线 smoke test 第一版。
- 项目计划文档和入口文档。

下一步：

- 扩展更多 source skills，例如课程、课件、视频、音频、儿童百科等资源来源。
- 将 smoke test 扩展为更系统的回归测试集。
- 继续增强 analyzer 的真实内容识别，例如 PDF 文本提取、图片 OCR、音视频字幕和媒体内容证据。
