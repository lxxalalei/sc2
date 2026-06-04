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
  -> 文件识别与归档
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
smartedu-textbooks -> learning-resource-analyzer -> learning-resource-ranker
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

### `smartedu-textbooks`

位置：[skills/smartedu-textbooks](skills/smartedu-textbooks)

当前已实现的官方资源站来源之一。负责从国家中小学智慧教育平台查找候选资源，输出标准候选资源，支持 token 下载 PDF，并把下载文件整理到资料库。后续新增来源应作为 source skill 接入统一评分流程。

模块调试命令和原爬虫脚本说明见：[docs/smartedu-textbooks-usage.md](docs/smartedu-textbooks-usage.md)

候选输出契约：

```text
learning-resource-candidate/v1
```

列出候选：

```bash
python3 skills/smartedu-textbooks/scripts/fetch_textbooks.py \
  --stage 小学 --grade 三年级 --subject 数学 --list-only \
  -o /tmp/smartedu-candidates.json
```

下载教材：

```bash
SMARTEDU_ACCESS_TOKEN='你的 access token' \
python3 skills/smartedu-textbooks/scripts/fetch_textbooks.py \
  --stage 小学 --grade 三年级 --subject 数学 --version 人教版 --volume 上册 \
  --library-dir 学习资料库
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

### `learning-resource-analyzer`

位置：[skills/learning-resource-analyzer](skills/learning-resource-analyzer)

负责对候选资源做格式识别、详情解析和内容证据提取，位于搜索和评分之间。第一版支持本地 HTML/TXT/PDF/DOCX/PPTX 的轻量分析，并为图片、音频、视频保留元数据分析入口。

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
- `learning-resource-intent` 第一版。
- `learning-resource-flow` 第一版。
- `learning-resource-ranker` 第一版。
- `learning-resource-selector` 第一版。
- `learning-resource-downloader` 第一版。
- `web-learning-search` 第一版。
- `learning-resource-analyzer` 第一版。
- 标准候选资源契约初版。
- 项目计划文档和入口文档。

下一步：

- 创建 `learning-library-organizer`，处理下载文件识别、命名和资料库归档。
- 设计资料库整理和外部索引 skill。
