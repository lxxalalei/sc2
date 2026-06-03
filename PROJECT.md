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

## 当前主线

目标是构建一套学习资源 agent 工作流：

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

当前已完成第一版官方教材来源 skill：

[skills/smartedu-textbooks](skills/smartedu-textbooks)
