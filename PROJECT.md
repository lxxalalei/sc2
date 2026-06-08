# 学习资源 Agent 项目入口

## 继续项目前必读

每次重新打开本项目或恢复工作时，先阅读：

[docs/learning-resource-agent-plan.md](docs/learning-resource-agent-plan.md)

该文档是本项目的主计划与进度档案，记录整体目标、skill 拆分、接口草案、当前完成状态和下一步计划。

## 工作要求

1. 开始新任务前，先根据计划文档恢复项目上下文。
2. 推进任何 skill、脚本、接口契约或资料库规则后，更新计划文档。
3. 计划文档应记录：
   - 已完成内容
   - 当前限制
   - 下一步任务
   - 重要设计决策
4. 最终资料库目录只放学习资源文件；索引、JSON、manifest、日志和缓存应放在工作目录或外部索引中。
5. 打包或较大改动后，优先运行 `python3 scripts/run_smoke_tests.py` 做离线回归验证。

## 当前主线

目标是构建一套学习资源 agent 工作流：

```text
用户需求
  -> 需求理解与澄清
  -> 本地资料库候选检索
  -> 多来源搜索
  -> 资源站发现与粗筛
  -> 资源站结构分析
  -> 资源分析与质量评分
  -> 用户选择
  -> 下载到工作缓存
  -> 文件识别、命名与归档
  -> 外部索引与去重
  -> 结构化学习资料库
```

当前已完成第一版主链路 skills：

- [skills/learning-resource-flow](skills/learning-resource-flow)
- [skills/learning-resource-intent](skills/learning-resource-intent)
- [skills/smartedu-resources](skills/smartedu-resources)
- [skills/web-learning-search](skills/web-learning-search)
- [skills/learning-resource-analyzer](skills/learning-resource-analyzer)
- [skills/learning-resource-ranker](skills/learning-resource-ranker)
- [skills/learning-resource-selector](skills/learning-resource-selector)
- [skills/learning-resource-downloader](skills/learning-resource-downloader)
- [skills/learning-library-organizer](skills/learning-library-organizer)
- [skills/learning-library-index](skills/learning-library-index)
- [skills/local-library-search](skills/local-library-search)
- [skills/resource-source-discovery](skills/resource-source-discovery)
- [skills/web-resource-profiler](skills/web-resource-profiler)
- [skills/generic-web-source](skills/generic-web-source)

下一步重点是继续完善 `smartedu-resources` 的站点级资源掌控能力，包括真实环境检索联调、搜索候选到详情 JSON 的追踪、教材 `tchMaterial` 内部适配迁移和更多栏目适配，同时增强 analyzer 的真实内容识别能力，例如 PDF 文本、图片 OCR、音视频字幕和媒体内容证据。

当前通用流程脚本已支持本地资料库外部索引优先检索、已优化 source 优先、web fallback、统一分析评分选择，以及用户确认编号后的下载、归档和外部索引更新。最终资料库仍只写入真实资源文件。

离线回归入口：

[scripts/run_smoke_tests.py](scripts/run_smoke_tests.py)
