---
name: learning-resource-selector
description: 将学习资源评分结果整理成用户可选择的候选清单。当 ranker 已输出 learning-resource-ranking/v1 后使用本 skill，把候选资源按推荐等级、格式、来源和风险整理为清晰选项，等待用户确认下载哪些资源；不负责搜索、评分、下载或归档。
---

# 学习资源候选选择

## 目标

接收 `learning-resource-ranker` 输出的排序结果，将其转换成用户能理解、可选择的候选清单。

本 skill 只负责：

- 整理候选展示。
- 生成选择编号。
- 说明推荐理由和风险。
- 给出下一步需要用户确认的动作。

本 skill 不负责搜索、评分、下载或归档。

## 输入

输入 `learning-resource-ranking/v1`：

```json
{
  "ranking_schema": "learning-resource-ranking/v1",
  "ranked_candidates": [],
  "rejected_candidates": [],
  "summary": {}
}
```

## 输出

输出 `learning-resource-selection/v1`，完整契约见 `references/selection-schema.md`。

核心结构：

```json
{
  "selection_schema": "learning-resource-selection/v1",
  "status": "awaiting_user_selection",
  "options": [],
  "hidden_options": [],
  "next_action": "请用户选择要下载的资源编号"
}
```

## 展示规则

- `excellent` 和 `high` 优先展示。
- `medium` 可作为备选展示。
- `low` 默认隐藏，除非候选数量不足。
- `reject` 不展示给普通用户，只放入 `hidden_options` 供调试。
- 每个选项必须包含标题、来源、格式、资源类型、评分、推荐理由、风险提示。
- 如果资源需要登录或授权，必须明确提示。
- 如果资源不可直接下载，应提示“可查看页面，下载需进一步确认”。

## 选择编号

默认使用：

```text
A, B, C, D...
```

用户可回复：

- `下载 A`
- `下载 A 和 B`
- `只要官方`
- `只要 PDF`
- `都不要，重新搜索`

selector 不执行这些动作，只把用户选择转换为后续 downloader 可消费的选择结果。

## 使用脚本

```bash
python3 skills/learning-resource-selector/scripts/select_candidates.py ranking.json
```

输出到文件：

```bash
python3 skills/learning-resource-selector/scripts/select_candidates.py \
  ranking.json -o selection.json
```

限制展示数量：

```bash
python3 skills/learning-resource-selector/scripts/select_candidates.py \
  ranking.json --max-options 5
```

## 回复规则

回复用户时不要直接贴完整 JSON。应简洁展示：

```text
找到 2 个较合适的资源：

A. 义务教育教科书 · 数学三年级上册
   来源：国家中小学智慧教育平台
   评分：81/high
   格式：PDF，类型：教材
   提示：需要登录或授权访问

B. ...

你想下载哪个？可以回复 A、B 或“都下载”。
```

如果没有可展示候选，说明没有找到合适资源，并建议重新澄清需求或换来源搜索。
