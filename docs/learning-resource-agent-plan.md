# 学习资源 Agent 项目计划与进度

更新时间：2026-06-04

## 项目目标

构建一套面向 3-12 岁儿童与家长的学习资源需求 agent 工作流：

1. 用户提出学习资源需求。
2. Agent 理解需求并在必要时追问澄清。
3. Agent 调用多个资源来源 skill 执行搜索。
4. 系统按统一评分机制评估候选资源质量。
5. Agent 将高质量候选资源提供给用户选择。
6. 用户确认后，系统下载资源到本地。
7. 系统识别文件内容、命名、分类并汇总进结构完整的资料库。

学习主题不局限于课内教材或教辅，也包括四则运算、拼音识字、儿童百科、唐诗宋词、儿歌、绘本、科学启蒙、艺术启蒙、逻辑思维等。资源格式不限于 PDF，后续需要支持 DOC/DOCX、PPT/PPTX、图片、音频、视频、网页快照、压缩包等。

## 总体架构

```text
用户需求
  -> learning-resource-flow          总控编排入口
  -> learning-resource-intent        需求理解与澄清
  -> source skills                   多来源搜索
  -> learning-resource-analyzer      候选详情分析与证据提取
  -> learning-resource-ranker        资源质量评分
  -> learning-resource-selector      用户候选展示与选择
  -> learning-resource-downloader    下载与缓存
  -> learning-library-organizer      文件识别、命名、归档
  -> learning-library-index          外部索引、去重、更新
  -> 学习资料库                       只存放最终资源文件
```

## 设计约束

- 所有 skill 的 `SKILL.md`、示例、面向 agent 的操作说明和 UI 元数据以中文为基本语言。
- 脚本内部可以保留必要的英文标识、命令参数和 JSON 字段名，便于程序处理和跨 skill 对接。
- 最终资料库目录只放学习资源文件；索引、JSON、manifest、日志和缓存应放在工作目录或外部索引中。
- 需求理解以“学习主题、孩子年龄/阶段、学习目标、资源形式”为中心；只有用户明确请求教材或课内同步资料时，才把教材版本、册次作为核心槽位。
- 资源来源不应和资源类型、学习主题、文件格式、年龄阶段或使用场景硬绑定；所有来源都应作为候选来源进入统一评分和选择流程。

## Skill 拆分

### 0. `learning-resource-flow`

职责：

- 作为 OpenClaw 接入时的总控入口。
- 判断学习资源请求应走哪些候选来源，来源选择保持类型无关、主题无关和格式无关。
- 串联 source skill、analyzer、ranker，避免只执行搜索不执行评分。
- 提供当前 SmartEdu 测试源的教材候选搜索、分析、评分、选择一键测试脚本。

状态：已创建第一版，当前 SmartEdu 测试源链路已跑通；正式教材请求应按多来源候选处理。

### 1. `learning-resource-intent`

职责：

- 理解用户自然语言需求。
- 抽取结构化槽位。
- 判断需求是否足够明确。
- 对模糊请求进行追问。
- 生成资源搜索计划。

关键槽位：

- 年龄/阶段：3-12 岁、学前、小学低年级、小学中年级、小学高年级等。
- 学习主题：四则整数运算、唐诗宋词、儿童百科、儿歌、科学实验等。
- 学习领域：数学、语文、英语、百科、文学、音乐、科学、艺术、综合素养等。
- 学习目标：启蒙、预习、复习、练习、拓展、阅读、听赏、查阅等。
- 资源类型：教材、课件、习题、试卷、视频、音频、图片、绘本、百科文章、游戏、教案等。
- 格式偏好：PDF、DOC/DOCX、PPT/PPTX、图片、音频、视频、网页、压缩包等。
- 教材附加槽位：版本/出版社、册次。仅在课内同步或教材需求中作为关键槽位。

状态：已创建第一版，已增加可执行任务契约。

### 2. Source Skills

每个来源单独做 skill，避免把搜索、下载、评分、归档耦合在一起。

已创建：

- `smartedu-textbooks`：当前已实现的官方教材来源之一，已支持候选列出、PDF 下载、资料库整理。
- `web-learning-search`：通用搜索结果标准化来源，已支持将 agent 搜索结果转为标准候选资源。

计划创建：

- `smartedu-resources`：国家中小学智慧教育平台课程、课件、视频等资源。
- `publisher-resources`：出版社官网资源。
- `edu-video-search`：学习视频搜索。
- `children-audio-search`：儿歌、诗词朗读、故事音频等儿童音频资源。
- `children-encyclopedia-search`：儿童百科、通识启蒙、图文知识资源。
- `local-library-search`：本地资料库检索。

Source skill 统一职责：

- 接收结构化查询。
- 搜索或爬取候选资源。
- 返回统一候选资源列表。
- 不直接决定最终质量排名。

状态：`smartedu-textbooks`、`web-learning-search` 已完成第一版，其余待创建。教材类请求后续应接入更多来源，不应只依赖当前测试源。

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

状态：已创建第一版，支持 `learning-resource-ranking/v1` 输出和启发式评分脚本。

### 4. `learning-resource-analyzer`

职责：

- 对候选资源做格式识别和详情解析。
- 从本地缓存文件、网页 HTML、文档压缩包 XML、媒体元数据中提取证据。
- 输出 `learning-resource-analysis/v1`，供 ranker 使用。
- 不搜索、不评分、不下载入库。

第一版支持：

- HTML/TXT 文本样本提取。
- PDF 页数粗略估计。
- DOCX/PPTX XML 文本提取和 PPTX 幻灯片数估计。
- 图片宽高轻量提取。
- 音频/视频 `ffprobe` 元数据入口。
- 风险词提示。

状态：已创建第一版。

### 5. `learning-resource-selector`

职责：

- 将候选资源以用户能理解的方式展示。
- 按类别、质量、格式和用途组织候选。
- 让用户确认要下载哪些资源。
- 支持“全部下载”“只下载官方”“只要 PPT/视频/习题”等选择。

状态：已创建第一版，支持 `learning-resource-selection/v1` 输出。

### 6. `learning-resource-downloader`

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
- 音频
- 视频
- HTML 页面快照
- ZIP/RAR/7z

状态：已创建第一版，支持 `learning-resource-download/v1` 输出；仅下载到工作缓存目录，不进入最终资料库。

### 7. `learning-library-organizer`

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

### 8. `learning-library-index`

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
  "learning_domain": "",
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
- 资源必须适合孩子年龄和理解水平，适龄性不明确则降权或追问。
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
- 支持 `--output` 将 JSON 摘要写入指定文件。
- 支持 token 访问 PDF 源文件。
- 支持 probe 测试。
- 支持下载 PDF。
- 支持按 `学段/年级/学科/版本/册次` 整理资料库。
- 下载摘要包含标准候选资源列表，成功下载的候选带 `local_file`，可交给 analyzer 分析本地 PDF。
- 最终资料库只保留 PDF。
- skill 结构校验通过。

当前限制：

- 只覆盖 SmartEdu 官方教材。
- 当前主要面向 PDF 教材。
- 还没有跨来源搜索和去重。

## 下一步计划

### P0：补齐基础契约

- [x] 为 `smartedu-textbooks` 增加标准候选资源输出格式。
- [x] 将 `--list-only` 输出调整为 ranker 可直接消费的结构。
- [x] 明确工作缓存目录和最终资料库目录的边界。
- [x] 为 `smartedu-textbooks` 增加 `--output`，并在下载候选中补充 `local_file`。

### P1：创建需求理解 skill

- [x] 创建 `learning-resource-flow` 总控编排 skill。
- [x] 为教材请求增加 `smartedu-textbooks -> analyzer -> ranker` 脚本化测试链路。
- [x] 创建 `learning-resource-intent`。
- [x] 设计槽位抽取规则。
- [x] 设计追问策略。
- [x] 给出 10 个典型用户请求测试样例。
- [x] 固化 `execution_tasks` 和 `ranking_profile` 输出契约，使用户需求可交给搜索、评分、下载流程。

### P2：创建评分 skill

- [x] 创建 `learning-resource-ranker`。
- [x] 固化评分字段和权重。
- [x] 实现候选资源排序输出。
- [x] 用 SmartEdu 教材候选做第一轮测试。
- [x] 让 ranker 消费 analyzer 产出的 `raw.analysis` 证据。

### P2.7：创建候选选择 skill

- [x] 创建 `learning-resource-selector`。
- [x] 固化 `learning-resource-selection/v1` 输出契约。
- [x] 将 ranker 结果转换成 A/B/C 用户可选清单。
- [x] 将教材 flow 的最终输出从 ranking 升级为 selection。

### P2.5：创建候选详情分析 skill

- [x] 创建 `learning-resource-analyzer`。
- [x] 固化 `learning-resource-analysis/v1` 输出契约。
- [x] 实现 HTML/TXT/PDF/DOCX/PPTX/图片/音频/视频的轻量分析入口。
- [ ] 用真实下载缓存文件做多格式样例测试。

### P3：创建资料库整理 skill

- [x] 创建 `learning-resource-downloader`。
- [x] 固化 `learning-resource-download/v1` 输出契约。
- [x] 实现用户选择编号到工作缓存下载的第一版脚本。
- [ ] 创建 `learning-library-organizer`。
- [ ] 支持多格式目录结构。
- [ ] 支持低置信度进入 `待确认/`。
- [ ] 设计资料库外部索引格式。

### P4：扩展资源类型和来源

- [x] 创建 `web-learning-search` 通用网页候选搜索 skill。
- [x] 支持从网页搜索结果推断 PDF/DOC/PPT/图片/音频/视频/网页等候选格式。
- [x] 将 `web-learning-search` 从内置搜索改为接收 agent 通用搜索结果并标准化候选。
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

### 2026-06-04

- 确认项目继续按“学习资源 Agent 工作流”推进。
- 将 `smartedu-textbooks` 的 `--list-only` 输出升级为 `learning-resource-candidate/v1` 标准候选资源格式。
- 创建 `learning-resource-intent` 第一版，负责需求理解、槽位抽取和追问策略。
- 明确新增约束：所有 skill 的主体说明、示例、面向 agent 的操作说明和 UI 元数据以中文为基本语言。
- 将 `learning-resource-intent` 和两个 skill 的 UI 元数据中文化。
- 将根目录 `README.md` 从单一爬虫说明重构为项目级首页，说明整体目标、当前 skills、资料库原则和下一步计划。
- 将原 README 中的 SmartEdu 爬虫用法迁移到 `docs/smartedu-textbooks-usage.md`，作为模块说明保留。
- 修正项目需求理解方向：目标用户是 3-12 岁儿童与家长，需求围绕随机学习主题展开，不默认限定为小学教材或教辅。
- 将 `learning-resource-intent` 重构为主题优先模型，优先澄清孩子年龄/阶段、核心主题、学习目标和资源形式；教材版本和册次只在教材类需求中作为关键槽位。
- 为 `learning-resource-intent` 增加 `references/test-cases.md`，沉淀 12 个典型用户请求及期望输出，用于后续回归检查。
- 为 `learning-resource-intent` 增加 `references/task-schema.md`，将输出从单纯意图抽取升级为可执行任务契约：`intent` 槽位负责理解需求，`execution_tasks` 负责驱动来源搜索，`ranking_profile` 负责传递评分偏好。
- 创建 `learning-resource-ranker` 第一版，负责对候选学习资源进行启发式质量评分、排序和风险解释；新增 `references/ranking-schema.md`、`references/test-cases.md` 和 `scripts/rank_candidates.py`。
- 使用 SmartEdu 人教版小学三年级数学教材候选测试 `learning-resource-ranker`，官方教材候选评分为 `high`，并正确提示需要登录或授权访问。
- 创建 `web-learning-search` 第一版，负责通用网页学习资源候选发现；新增候选格式说明、测试样例、本地搜索结果 fixture 和 `scripts/search_web_resources.py`。
- 验证 `web-learning-search -> learning-resource-ranker` 最小链路：可打印四则混合运算 PDF 练习题评为 `high`，无关恐龙视频降为 `low`，包含下载器/破解风险的候选进入 `rejected_candidates`。
- 修正通用网页候选元数据策略：source skill 不得把用户 filters 直接写入每个候选的主题、学科和阶段字段，避免无关搜索结果被 ranker 误判为匹配。
- 创建 `learning-resource-analyzer` 第一版，位于 source skill 与 ranker 之间，负责对候选资源做格式识别、详情解析和内容证据提取；新增 `analysis-schema.md`、测试样例、样例候选和 `scripts/analyze_candidates.py`。
- 为 `smartedu-textbooks` 增加 `--output` 文件输出；下载模式摘要也输出 `learning-resource-candidate/v1` 候选列表，下载成功的候选带 `local_file`，用于 analyzer 分析本地 PDF。
- 将当前版本整理为 OpenClaw 可加载技能包，输出到 `dist/openclaw-learning-resource-skills-20260604/` 和 `dist/openclaw-learning-resource-skills-20260604.tar.gz`；包内只包含 skills、必要说明、schema、测试判例和脚本，不包含 `data/`、`downloads/`、资料库、缓存、token 或日志。
- 修复 OpenClaw 测试中教材命令只触发搜索、不继续执行分析和排名的问题：新增 `learning-resource-flow` 总控编排 skill，并提供 `scripts/run_textbook_flow.py`，实测可输出 `learning-resource-ranking/v1`。
- 创建 `learning-resource-selector` 第一版，负责把 `learning-resource-ranking/v1` 转换为 `learning-resource-selection/v1` 用户可选清单；教材 flow 已接入 selector，实测可输出 A/B 候选、评分摘要、登录授权提示和下一步选择动作。
- 优化 `web-learning-search`：去掉内置固定搜索引擎依赖，改为默认接收 agent 通用搜索结果 JSON，只负责标准化为 `learning-resource-candidate/v1`；HTML 解析仅保留为本地调试入口。
- 调整来源策略：任何资源类型、主题或格式都不与单一 source 硬绑定；已实现来源只作为候选来源进入统一分析、评分和选择流程。
- 创建 `learning-resource-downloader` 第一版，负责根据 selector 选项编号下载资源到工作缓存目录；已验证授权资源会被安全跳过、无效编号会进入失败列表。本地 HTTP 直链下载测试受当前沙箱监听端口限制，留待具备网络/服务权限环境验证。
