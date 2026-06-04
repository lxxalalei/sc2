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
- `smartedu-textbooks`：国家中小学智慧教育平台官方教材候选和下载。
- `web-learning-search`：通用网页学习资源候选搜索。
- `learning-resource-analyzer`：候选详情分析。
- `learning-resource-ranker`：候选质量评分排序。
- `learning-resource-selector`：把评分结果整理成用户可选择的清单。
- `learning-resource-downloader`：根据用户选择下载到工作缓存目录。

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
  -> source skills 候选搜索
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
  -> 给用户展示排序后的候选
  -> 用户确认后进入 learning-resource-downloader
```

当前已实现的相关来源包括 `smartedu-textbooks`，它应被看作普通 source skill。后续新增其他来源后，应一起进入候选和评分。

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
  -> web-learning-search
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
  -> 给用户展示排序后的候选
  -> 用户确认后进入 learning-resource-downloader
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
smartedu-textbooks list-only  # 当前测试 source
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
