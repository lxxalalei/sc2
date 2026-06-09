# 学习资源需求理解测试样例

这些样例用于校验 `learning-resource-intent` 是否能围绕 3-12 岁儿童学习主题进行理解、追问和搜索计划生成。

测试时重点看六件事：

1. 是否正确识别核心学习主题。
2. 是否正确判断年龄/阶段是否缺失。
3. 是否只在必要时追问。
4. 是否避免把单一资源类型当成默认判断起点。
5. `ready` 时是否生成可执行的 `execution_tasks`。
6. `execution_tasks` 是否包含 `target_skill`、`query`、`filters`、`download_policy`，能直接交给搜索和评分流程。

## 样例 1：宽泛数学资料

用户请求：

```text
帮我找点数学学习资料
```

期望：

```json
{
  "status": "needs_clarification",
  "learning_domain": "数学",
  "core_topic": null,
  "missing_slots": ["learner_age_or_grade", "core_topic", "resource_goal_or_type"],
  "clarifying_questions": ["孩子大概几岁或几年级？", "想学哪个数学主题？", "需要讲解、练习题还是视频？"]
}
```

## 样例 2：明确主题但缺年龄

用户请求：

```text
我要四则整数运算的学习资料
```

期望：

```json
{
  "status": "needs_clarification",
  "learning_domain": "数学",
  "core_topic": "四则整数运算",
  "missing_slots": ["learner_age_or_grade", "resource_goal_or_type"],
  "clarifying_questions": ["孩子大概几岁或几年级？", "你想要讲解资料、练习题，还是视频？"]
}
```

## 样例 3：主题、年龄、形式明确

用户请求：

```text
给 8 岁孩子找四则混合运算练习题，最好能打印
```

期望：

```json
{
  "status": "ready",
  "learner_age": 8,
  "learning_domain": "数学",
  "core_topic": "四则混合运算",
  "resource_goal": "练习",
  "resource_types": ["习题"],
  "format_preferences": ["pdf", "doc"],
  "constraints": ["适合打印"],
  "execution_tasks": [
    {
      "target_skill": "web-learning-search",
      "action": "search",
      "query": "8岁 四则混合运算 练习题 可打印 PDF",
      "filters": {"learner_age": 8, "core_topic": "四则混合运算", "resource_types": ["习题"], "printable": true},
      "download_policy": "after_user_selection"
    }
  ]
}
```

## 样例 4：儿童百科过宽

用户请求：

```text
找点儿童百科
```

期望：

```json
{
  "status": "needs_clarification",
  "learning_domain": "百科",
  "core_topic": "儿童百科",
  "resource_goal": "拓展",
  "missing_slots": ["learner_age", "subtopics", "resource_types"],
  "clarifying_questions": ["孩子几岁？", "更想看动物、恐龙、宇宙、人体，还是综合百科？", "需要图文、视频还是音频？"]
}
```

## 样例 5：百科主题明确

用户请求：

```text
找适合 7 岁孩子看的恐龙百科视频
```

期望：

```json
{
  "status": "ready",
  "learner_age": 7,
  "learning_domain": "百科",
  "core_topic": "恐龙百科",
  "subtopics": ["恐龙"],
  "resource_goal": "拓展",
  "resource_types": ["视频"],
  "difficulty": "适龄",
  "execution_tasks": [
    {
      "target_skill": "web-learning-search",
      "action": "search",
      "query": "7岁 恐龙百科 视频 儿童",
      "filters": {"learner_age": 7, "core_topic": "恐龙百科", "resource_types": ["视频"]},
      "download_policy": "after_user_selection"
    }
  ]
}
```

## 样例 6：唐诗宋词启蒙音频

用户请求：

```text
给 5 岁孩子找唐诗宋词启蒙音频
```

期望：

```json
{
  "status": "ready",
  "learner_age": 5,
  "stage": "学前",
  "learning_domain": "文学",
  "core_topic": "唐诗宋词启蒙",
  "resource_goal": "听赏",
  "resource_types": ["音频"],
  "difficulty": "启蒙",
  "execution_tasks": [
    {
      "target_skill": "web-learning-search",
      "action": "search",
      "query": "5岁 唐诗宋词启蒙 音频 儿童",
      "filters": {"learner_age": 5, "core_topic": "唐诗宋词启蒙", "resource_types": ["音频"]},
      "download_policy": "after_user_selection"
    }
  ]
}
```

## 样例 7：儿歌资源缺形式偏好但可搜索

用户请求：

```text
给 4 岁孩子找几首英文儿歌
```

期望：

```json
{
  "status": "ready",
  "learner_age": 4,
  "stage": "学前",
  "learning_domain": "音乐",
  "core_topic": "英文儿歌",
  "resource_goal": "听赏",
  "resource_types": ["音频", "视频", "歌词"],
  "difficulty": "启蒙",
  "execution_tasks": [
    {
      "target_skill": "web-learning-search",
      "action": "search",
      "query": "4岁 英文儿歌 音频 视频 歌词",
      "filters": {"learner_age": 4, "core_topic": "英文儿歌", "resource_types": ["音频", "视频", "歌词"]},
      "download_policy": "after_user_selection"
    }
  ]
}
```

## 样例 8：幼小衔接场景

用户请求：

```text
孩子快上一年级了，想做幼小衔接
```

期望：

```json
{
  "status": "needs_clarification",
  "stage": "学前",
  "learner_profile": "幼小衔接",
  "resource_goal": "启蒙",
  "missing_slots": ["learning_domain", "resource_types"],
  "clarifying_questions": ["更想先做拼音识字、数学启蒙，还是习惯养成？", "需要练习册、视频，还是亲子活动资料？"]
}
```

## 样例 9：儿童百科视频和图文

用户请求：

```text
帮孩子找恐龙百科视频和图文资料
```

期望：

```json
{
  "status": "needs_clarification",
  "learning_domain": "百科",
  "core_topic": "恐龙百科",
  "resource_types": ["视频", "百科文章", "图片"],
  "missing_slots": ["learner_age_or_grade"],
  "clarifying_questions": ["孩子大概几岁或几年级？"]
}
```

## 样例 10：可打印练习题，多来源候选

用户请求：

```text
给 8 岁孩子找可打印四则混合运算练习题
```

期望：

```json
{
  "status": "ready",
  "learner_age": 8,
  "stage": "小学低年级",
  "learning_domain": "数学",
  "subject": "数学",
  "core_topic": "四则混合运算",
  "resource_goal": "练习",
  "resource_types": ["习题"],
  "format_preferences": ["pdf"],
  "constraints": ["适合打印"],
  "execution_tasks": [
    {
      "target_skill": "local-library-search",
      "action": "search",
      "query": "8岁 四则混合运算 可打印练习题",
      "download_policy": "never"
    },
    {
      "target_skill": "web-learning-search",
      "action": "search",
      "query": "8岁 四则混合运算 可打印练习题 PDF",
      "download_policy": "after_user_selection"
    }
  ]
}
```

## 样例 11：本地资料库优先

用户请求：

```text
看看本地有没有适合 6 岁孩子的识字资料
```

期望：

```json
{
  "status": "ready",
  "learner_age": 6,
  "learning_domain": "语文",
  "core_topic": "识字",
  "resource_goal": "启蒙",
  "source_preferences": ["本地资料库"],
  "execution_tasks": [
    {
      "target_skill": "local-library-search",
      "action": "search",
      "query": "6岁 识字 启蒙 本地资料",
      "filters": {"learner_age": 6, "core_topic": "识字"},
      "download_policy": "never"
    }
  ]
}
```

## 样例 12：家长要求过宽且下载

用户请求：

```text
帮我把适合 6 岁孩子的学习资料都下载下来
```

期望：

```json
{
  "status": "needs_clarification",
  "learner_age": 6,
  "missing_slots": ["core_topic", "resource_goal", "resource_types"],
  "clarifying_questions": ["想围绕哪个主题？比如识字、数学启蒙、英语、百科或儿歌。", "需要文档、图片、音频还是视频？"]
}
```
