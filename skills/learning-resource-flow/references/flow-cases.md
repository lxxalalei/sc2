# 工作流测试用例

## 用例 1：可打印练习题候选排序

用户：

```text
给 8 岁孩子找四则混合运算可打印练习题
```

期望：

```text
learning-resource-intent
  -> local-library-search           # 如已有外部索引，先检索本地候选
  -> smartedu-resources site-profile
  -> smartedu-resources             # 已优化站点 source 之一
  -> web-learning-search            # SmartEdu 候选不足或用户需要更多来源时再进入
  -> resource-source-discovery      # 对通用搜索结果中的资源站做粗筛
  -> web-resource-profiler          # 对高价值来源做结构分析
  -> generic-web-source             # 仅对可通用抽取来源生成直链候选
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

最终应返回多来源可选项，并给出评分、来源、格式、可打印性和访问风险提示。

## 用例 2：儿童百科视频和图文

用户：

```text
帮孩子找恐龙百科视频和图文资料
```

期望：

先澄清孩子年龄或年级；需求明确后，通过本地索引、已优化来源和 web fallback 生成候选，视频和图文资料统一进入 analyzer/ranker/selector，不按格式分裂流程。

## 用例 3：用户确认后下载归档

用户：

```text
下载 A 和 C
```

期望：

基于上一次 selection 结果继续执行。若用户选择的候选来源明确、可下载且授权条件满足，再执行下载；下载后候选带 `local_file`，可交给 analyzer 分析本地文件。

下载完成后进入 `learning-library-organizer`，只将真实资源文件归档到最终资料库，归档 JSON 留在工作目录。归档完成后进入 `learning-library-index`，在资料库外部更新索引和去重记录。

## 用例 4：主题资源

用户：

```text
给 8 岁孩子找四则混合运算可打印练习题
```

期望：

```text
learning-resource-intent
  -> local-library-search           # 如已有外部索引，先检索本地候选
  -> smartedu-resources site-profile
  -> smartedu-resources             # 先查已优化官方平台 source
  -> candidate threshold check
  -> web-learning-search            # 候选太少或质量不足时再进入
  -> resource-source-discovery
  -> web-resource-profiler
  -> generic-web-source             # 仅对简单资源站直链资源生成候选
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

不要直接下载搜索结果。

用户确认下载后，先进入 `learning-resource-downloader` 保存到工作缓存，再由 `learning-library-organizer` 按元数据和文件证据整理入库，最后由 `learning-library-index` 更新外部索引。

## 用例 5：本地已有资料

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

## 用例 6：大量搜索结果粗筛

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

## 用例 7：已优化来源不足后网络补充

用户：

```text
给 8 岁孩子找可打印四则混合运算练习题
```

期望：

```text
learning-resource-intent
  -> smartedu-resources site-profile
  -> smartedu-resources search-resources
  -> 若候选少于阈值
  -> agent web search
  -> web-learning-search
  -> learning-resource-analyzer
  -> learning-resource-ranker
  -> learning-resource-selector
```

如果当前环境不能联网搜索，流程应输出 `needs_web_search=true` 和建议查询词，由 agent 使用自身搜索能力获取搜索结果后继续，而不是在 source skill 内强制绑定某个搜索引擎。
