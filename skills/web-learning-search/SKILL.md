---
name: web-learning-search
description: 根据结构化学习资源任务执行通用网页候选发现，面向 3-12 岁儿童与家长的主题学习资料搜索，例如四则运算练习、儿童百科、唐诗宋词、儿歌、绘本、科学启蒙、课件、图片、音频、视频、网页资料等。用于返回候选资源列表，不负责评分、下载或归档。
---

# 通用网页学习资源候选标准化

## 目标

根据 `learning-resource-intent` 生成的 `execution_tasks` 和 agent 已获得的通用搜索结果，提取学习资源候选，并输出统一的 `learning-resource-candidate/v1` 列表。

本 skill 是 source skill，只负责候选发现：

- 不判断最终质量排名。
- 不下载资源文件。
- 不写入最终资料库。
- 不绕过登录、付费、版权或访问限制。

## 输入

优先接收 `execution_tasks` 中目标为 `web-learning-search` 的任务：

```json
{
  "task_id": "task_001",
  "task_type": "source_search",
  "target_skill": "web-learning-search",
  "action": "search",
  "query": "8岁 四则混合运算 练习题 可打印 PDF",
  "filters": {
    "learner_age": 8,
    "subject": "数学",
    "core_topic": "四则混合运算",
    "resource_types": ["习题"],
    "printable": true
  },
  "expected_resource_types": ["习题"],
  "expected_formats": ["PDF", "DOC/DOCX"],
  "download_policy": "after_user_selection"
}
```

也可以接收包含 `query` 和 `filters` 的简化 JSON。

实际搜索由 agent 的通用搜索能力完成。本 skill 不指定搜索引擎，只负责把搜索结果标准化为候选资源。

搜索结果输入格式：

```json
{
  "query": "8岁 四则混合运算 练习题 可打印 PDF",
  "filters": {"learner_age": 8, "core_topic": "四则混合运算"},
  "search_results": [
    {
      "title": "8岁四则混合运算可打印练习题 PDF",
      "url": "https://example.edu.cn/math.pdf",
      "snippet": "适合小学低年级儿童的数学练习，可直接打印。"
    }
  ]
}
```

## 输出

输出统一候选格式：

```json
{
  "candidate_schema": "learning-resource-candidate/v1",
  "source_skill": "web-learning-search",
  "query": "",
  "filters": {},
  "candidates": []
}
```

候选字段说明见 `references/candidate-schema.md`。

## 查询生成策略

需要 agent 搜索时，优先使用任务中的 `query`。如果没有 `query`，根据 `filters` 拼出搜索句：

- 年龄/年级
- 核心主题
- 资源类型
- 格式偏好
- 使用场景，例如可打印、音频、视频、亲子共读

示例：

- `8岁 四则混合运算 练习题 可打印 PDF`
- `7岁 恐龙百科 视频 儿童`
- `5岁 唐诗宋词启蒙 音频`
- `小学 三年级 分数初步认识 课件 PPT`

## 候选识别

对搜索结果提取：

- 标题
- URL
- 摘要
- 来源站点
- 可能的文件格式
- 可能的资源类型
- 是否看起来可下载
- 元数据置信度

文件格式可从 URL、标题、摘要中推断：`pdf`、`doc/docx`、`ppt/pptx`、`image`、`audio`、`video`、`html`、`zip`。

资源类型可从标题和摘要中推断：习题、试卷、课件、视频、音频、图片、绘本、百科文章、讲义、素材、网页等。

## 风险边界

- 搜索结果只是候选，不代表推荐。
- 来源不明、强制下载器、疑似侵权、成人化、广告化资源不要直接下载。
- 需要登录或付费的资源可以作为候选，但要标记 `requires_auth` 或在 `raw.warnings` 中说明。
- 搜索结果必须交给 `learning-resource-ranker` 排序后再展示给用户。

## 使用脚本

从 agent 搜索结果 JSON 读取：

```bash
python3 skills/web-learning-search/scripts/search_web_resources.py \
  --search-results-json search-results.json \
  --task-json task.json
```

从任务 JSON 读取：

```bash
python3 skills/web-learning-search/scripts/search_web_resources.py \
  --task-json task.json \
  --limit 10
```

本地调试 HTML 解析：

```bash
python3 skills/web-learning-search/scripts/search_web_resources.py \
  --query "7岁 恐龙百科 视频 儿童" \
  --html-file fixtures/search.html
```

脚本输出 `learning-resource-candidate/v1` JSON。后续应把该输出交给 `learning-resource-analyzer` 和 `learning-resource-ranker`。
