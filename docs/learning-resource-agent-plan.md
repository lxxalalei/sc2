# 学习资源 Agent 项目计划与进度

更新时间：2026-06-03

## 项目目标

构建一套面向学习资源需求的 agent 工作流：

1. 用户提出学习资源需求。
2. Agent 理解需求并在必要时追问澄清。
3. Agent 调用多个资源来源 skill 执行搜索。
4. 系统按统一评分机制评估候选资源质量。
5. Agent 将高质量候选资源提供给用户选择。
6. 用户确认后，系统下载资源到本地。
7. 系统识别文件内容、命名、分类并汇总进结构完整的资料库。

资源格式不限于 PDF，后续需要支持 DOC/DOCX、PPT/PPTX、图片、视频、网页快照、压缩包等。

## 总体架构

```text
用户需求
  -> learning-resource-intent        需求理解与澄清
  -> source skills                   多来源搜索
  -> learning-resource-ranker        资源质量评分
  -> learning-resource-selector      用户候选展示与选择
  -> learning-resource-downloader    下载与缓存
  -> learning-library-organizer      文件识别、命名、归档
  -> learning-library-index          外部索引、去重、更新
  -> 学习资料库                       只存放最终资源文件
```

## Skill 拆分

### 1. `learning-resource-intent`

职责：

- 理解用户自然语言需求。
- 抽取结构化槽位。
- 判断需求是否足够明确。
- 对模糊请求进行追问。
- 生成资源搜索计划。

关键槽位：

- 学段：小学、初中、高中、大学、职业教育等。
- 年级：一年级、三年级、七年级、高一等。
- 学科：语文、数学、英语、科学、物理等。
- 主题：单元、知识点、章节、考试类型等。
- 资源类型：教材、课件、习题、试卷、视频、图片、教案等。
- 版本/出版社：人教版、统编版、北师大版等。
- 册次：上册、下册、全一册、必修等。
- 使用场景：预习、复习、备课、练习、讲解、考试等。

状态：待创建。

### 2. Source Skills

每个来源单独做 skill，避免把搜索、下载、评分、归档耦合在一起。

已创建：

- `smartedu-textbooks`：国家中小学智慧教育平台官方教材来源，已支持候选列出、PDF 下载、资料库整理。

计划创建：

- `smartedu-resources`：国家中小学智慧教育平台课程、课件、视频等资源。
- `publisher-resources`：出版社官网资源。
- `web-learning-search`：通用网页学习资源搜索。
- `edu-video-search`：学习视频搜索。
- `local-library-search`：本地资料库检索。

Source skill 统一职责：

- 接收结构化查询。
- 搜索或爬取候选资源。
- 返回统一候选资源列表。
- 不直接决定最终质量排名。

状态：`smartedu-textbooks` 已完成第一版，其余待创建。

### 3. `learning-resource-ranker`

职责：

- 对候选资源打分。
- 解释评分依据。
- 输出排序后的资源清单。

评分维度草案：

```json
{
  "authority_score": 0.0,
  "relevance_score": 0.0,
  "freshness_score": 0.0,
  "completeness_score": 0.0,
  "format_score": 0.0,
  "accessibility_score": 0.0,
  "safety_score": 0.0,
  "pedagogical_score": 0.0,
  "final_score": 0.0,
  "reason": ""
}
```

初始权重建议：

- 权威性：20%
- 相关性：30%
- 完整性：15%
- 可访问性：10%
- 教学适用性：15%
- 安全性：10%

状态：待创建。

### 4. `learning-resource-selector`

职责：

- 将候选资源以用户能理解的方式展示。
- 按类别、质量、格式和用途组织候选。
- 让用户确认要下载哪些资源。
- 支持“全部下载”“只下载官方”“只要 PPT/视频/习题”等选择。

状态：待创建。

### 5. `learning-resource-downloader`

职责：

- 执行通用下载。
- 支持多格式文件。
- 支持 token、cookie、登录态。
- 支持失败重试和去重。
- 下载结果进入工作缓存目录，不直接进入资料库。

支持格式目标：

- PDF
- DOC/DOCX
- PPT/PPTX
- XLS/XLSX
- 图片
- 视频
- HTML 页面快照
- ZIP/RAR/7z

状态：待创建。

### 6. `learning-library-organizer`

职责：

- 识别文件类型。
- 从文件名、网页元数据、文件内容中提取标题和分类。
- PDF/Word/PPT 文本提取。
- 图片 OCR。
- 视频元数据、标题、字幕提取。
- 低置信度分类进入待确认区。
- 将资源移动到最终资料库。

资料库建议结构：

```text
学习资料库/
  学段/
    年级/
      学科/
        版本或来源/
          册次或主题/
            资源类型/
              文件名
  待确认/
```

示例：

```text
学习资料库/小学/三年级/数学/人教版/上册/教材/义务教育教科书·数学三年级上册_33c8d495.pdf
学习资料库/小学/三年级/数学/未确认版本/分数初步认识/课件/分数初步认识.pptx
学习资料库/待确认/source_xxxxxxxx.pdf
```

状态：待创建。

### 7. `learning-library-index`

职责：

- 在资料库外部维护索引。
- 支持去重、检索、更新、来源追踪。
- 资料库目录只保留最终资源文件，索引 JSON/SQLite 不放入资料库。

索引字段草案：

```json
{
  "file_path": "",
  "source_url": "",
  "source_name": "",
  "resource_type": "",
  "stage": "",
  "grade": "",
  "subject": "",
  "version": "",
  "volume": "",
  "topic": "",
  "quality_score": 0.0,
  "classification_confidence": 0.0,
  "download_time": "",
  "hash": "",
  "evidence": []
}
```

状态：待创建。

## 统一候选资源格式草案

所有 source skill 应尽量输出如下结构，供 ranker 消费：

```json
{
  "source": "smartedu-textbooks",
  "source_url": "",
  "resource_id": "",
  "title": "",
  "resource_type": "pdf",
  "stage": "",
  "grade": "",
  "subject": "",
  "version": "",
  "volume": "",
  "topic": "",
  "provider": "",
  "official": true,
  "downloadable": true,
  "requires_auth": true,
  "format": "pdf",
  "size": 0,
  "metadata_confidence": 0.0,
  "raw": {}
}
```

## 质量评分原则

基础判断：

- 官方来源优先，但不等于总是最适合。
- 资源必须与用户目标相关，相关性低则降权。
- 来路不明、强制跳转、疑似侵权或可疑下载源应降权或排除。
- 格式要匹配用户使用场景：备课优先 PPT/教案，学习优先教材/视频/习题。
- 对不完整资源、缺页资源、无标题资源要降权。

低置信度策略：

- 分类置信度高于 0.85：自动归档。
- 0.60 到 0.85：进入待确认或询问用户。
- 低于 0.60：只保留来源 ID 和原始文件，等待确认。

## 当前已完成

### `smartedu-textbooks`

完成时间：2026-06-03

已实现：

- 抓取国家中小学智慧教育平台教材索引。
- 支持 `--list-only` 候选列出。
- 支持 token 访问 PDF 源文件。
- 支持 probe 测试。
- 支持下载 PDF。
- 支持按 `学段/年级/学科/版本/册次` 整理资料库。
- 最终资料库只保留 PDF。
- skill 结构校验通过。

当前限制：

- 只覆盖 SmartEdu 官方教材。
- 当前主要面向 PDF 教材。
- 质量评分尚未独立为 ranker。
- 还没有统一候选输出字段的完整实现。
- 还没有跨来源搜索和去重。

## 下一步计划

### P0：补齐基础契约

- [ ] 为 `smartedu-textbooks` 增加标准候选资源输出格式。
- [ ] 将 `--list-only` 输出调整为 ranker 可直接消费的结构。
- [ ] 明确工作缓存目录和最终资料库目录的边界。

### P1：创建需求理解 skill

- [ ] 创建 `learning-resource-intent`。
- [ ] 设计槽位抽取规则。
- [ ] 设计追问策略。
- [ ] 给出 10 个典型用户请求测试样例。

### P2：创建评分 skill

- [ ] 创建 `learning-resource-ranker`。
- [ ] 固化评分字段和权重。
- [ ] 实现候选资源排序输出。
- [ ] 用 SmartEdu 教材候选做第一轮测试。

### P3：创建资料库整理 skill

- [ ] 创建 `learning-library-organizer`。
- [ ] 支持多格式目录结构。
- [ ] 支持低置信度进入 `待确认/`。
- [ ] 设计资料库外部索引格式。

### P4：扩展资源类型和来源

- [ ] 支持 PPT/DOC/图片/视频。
- [ ] 创建更多 source skills。
- [ ] 引入本地资料库检索。

## 进度日志

### 2026-06-03

- 完成 SmartEdu 官方教材爬虫。
- 验证人教版小学三年级数学上册 PDF 可下载。
- 创建 `smartedu-textbooks` skill。
- 增强 skill 的需求澄清逻辑。
- 增加 `--list-only` 候选清单模式。
- 创建本项目计划与进度文档。
- 创建根目录 `PROJECT.md` 作为下次恢复项目的入口文档，要求每次继续工作前读取本计划文档。
