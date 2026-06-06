# 工作流测试用例

## 用例 1：教材候选排序

用户：

```text
帮我查找小学三年级数学人教版教材
```

期望：

```text
learning-resource-intent
  -> local-library-search           # 如已有外部索引，先检索本地候选
  -> smartedu-resources             # SmartEdu 站点级 source，教材是站内资源分支
  -> web-learning-search            # 当 agent 已有通用搜索结果时标准化其他候选
  -> resource-source-discovery      # 对通用搜索结果中的资源站做粗筛
  -> web-resource-profiler          # 对高价值来源做结构分析
  -> generic-web-source             # 仅对可通用抽取来源生成直链候选
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

先通过多个可用来源生成候选并完成评分选择。SmartEdu 站点候选统一来自 `smartedu-resources`；若用户选择的候选来源明确、可下载且授权条件满足，再执行下载；下载后候选带 `local_file`，可交给 analyzer 分析本地文件。

下载完成后进入 `learning-library-organizer`，只将真实资源文件归档到最终资料库，归档 JSON 留在工作目录。归档完成后进入 `learning-library-index`，在资料库外部更新索引和去重记录。

## 用例 3：主题资源

用户：

```text
给 8 岁孩子找四则混合运算可打印练习题
```

期望：

```text
learning-resource-intent
  -> local-library-search           # 如已有外部索引，先检索本地候选
  -> smartedu-resources             # SmartEdu 官方平台资源可作为候选来源之一
  -> web-learning-search
  -> resource-source-discovery
  -> web-resource-profiler
  -> generic-web-source             # 仅对简单资源站直链资源生成候选
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

不要直接下载搜索结果。

用户确认下载后，先进入 `learning-resource-downloader` 保存到工作缓存，再由 `learning-library-organizer` 按元数据和文件证据整理入库，最后由 `learning-library-index` 更新外部索引。

## 用例 4：本地已有资料

用户：

```text
找一下四则混合运算练习题
```

期望：

```text
learning-resource-intent
  -> local-library-search
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

如果本地候选质量足够高，先展示本地候选；如果本地无命中或质量不足，再继续调用其他 source skills。

## 用例 5：大量搜索结果粗筛

用户：

```text
给 8 岁孩子找可打印数学练习题
```

期望：

```text
learning-resource-intent
  -> web-learning-search
  -> resource-source-discovery
  -> web-resource-profiler
  -> generic-web-source             # 对简单资源站直链资源生成候选
  -> 复杂高价值来源沉淀独立 source skill
  -> learning-resource-analyzer
  -> learning-resource-ranker
```

明显下载器、破解、广告或成人化来源应进入 `rejected_sources`。
