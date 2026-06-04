# 工作流测试用例

## 用例 1：教材候选排序

用户：

```text
帮我查找小学三年级数学人教版教材
```

期望：

```text
learning-resource-intent
  -> smartedu-textbooks list-only   # 当前测试 source，可与其他教材来源并行
  -> web-learning-search            # 当 agent 已有通用搜索结果时标准化其他候选
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

最终应返回多来源可选项，并给出评分、来源、格式和“需要登录或授权访问”等提示。

## 用例 2：明确教材下载

用户：

```text
下载人教版小学三年级数学上册
```

期望：

先通过多个可用来源生成候选并完成评分选择。当前测试源可以包含 `smartedu-textbooks`。若用户选择的候选来源明确、可下载且授权条件满足，再执行下载；下载后候选带 `local_file`，可交给 analyzer 分析本地文件。

## 用例 3：主题资源

用户：

```text
给 8 岁孩子找四则混合运算可打印练习题
```

期望：

```text
learning-resource-intent
  -> web-learning-search
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

不要直接下载搜索结果。
