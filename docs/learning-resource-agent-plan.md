# 学习资源 Agent 项目计划与进度

更新时间：2026-06-08

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
  -> local-library-search            本地已有资料候选检索
  -> source skills                   多来源搜索
  -> resource-source-discovery       资源站发现与来源级粗筛
  -> web-resource-profiler           资源站结构分析与接入策略
  -> generic-web-source              简单资源站直链候选抽取
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
- 打包或较大改动后，优先运行 `python3 scripts/run_smoke_tests.py` 做离线回归验证。

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

每个资源站点原则上做成一个站点级 source skill，避免把同一站点内的某个资源类型误拆成独立来源。站点 skill 应掌控本资源站内的栏目、搜索、详情、资源类型和内部适配器。

已创建：

- `smartedu-resources`：国家中小学智慧教育平台站点级资源入口，已支持站点能力画像、栏目画像、栏目路由图、栏目扫描、站点批量扫描、页面 HTML/JS 线索画像、站内搜索候选归一化、搜索候选详情追踪、站内教材候选和详情 `ti_items` 候选解析；教材 `tchMaterial` 是其中一种站内资源分支。
- `smartedu-textbooks`：早期教材 PDF 兼容适配资产，保留已跑通的候选、下载和资料库整理脚本；不再作为 OpenClaw 外部路由的独立资源站来源。
- `web-learning-search`：通用搜索结果标准化来源，已支持将 agent 搜索结果转为标准候选资源。
- `resource-source-discovery`：从搜索结果或网页候选中识别资源站候选，做来源级粗筛。
- `web-resource-profiler`：对高价值资源站做 HTML/JS/API/分页/详情/下载链接和登录限制分析。
- `generic-web-source`：对 profiler 判定为简单资源站的页面抽取资源直链候选。
- `local-library-search`：基于资料库外部索引检索本地已有学习资源候选。

计划创建：

- `publisher-resources`：出版社官网资源。
- `edu-video-search`：学习视频搜索。
- `children-audio-search`：儿歌、诗词朗读、故事音频等儿童音频资源。
- `children-encyclopedia-search`：儿童百科、通识启蒙、图文知识资源。

Source skill 统一职责：

- 接收结构化查询。
- 搜索或爬取候选资源。
- 返回统一候选资源列表。
- 不直接决定最终质量排名。

状态：`smartedu-resources`、`web-learning-search`、`resource-source-discovery`、`web-resource-profiler`、`generic-web-source`、`local-library-search` 已完成第一版，其余待创建。`smartedu-resources` 当前可输出站点能力画像、栏目路由图和页面线索画像，可按栏目路由执行候选扫描或批量扫描多个栏目，并把 SmartEdu 栏目、搜索结果、搜索候选详情、教材候选和详情文件项统一转为候选；在线搜索接口在命令行环境可能受 WAF/登录态影响，OpenClaw 或账号态运行时应传入可用 endpoint/token/header，上线前继续做真实环境联调。

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
- 图片宽高轻量提取，支持 PIL 或 PNG/GIF/JPEG 文件头回退解析。
- 音频/视频 `ffprobe` 元数据入口。
- 风险词提示。

状态：已创建第一版，并已通过离线多格式样例覆盖 DOCX、PPTX、PNG 和 HTML 风险页。

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
- 将资源复制或移动到最终资料库。

资料库建议结构：

```text
学习资料库/
  学段或适龄/
    年级或阶段/
      学习领域或学科/
        主题或资源类型/
          来源或版本/
            文件名
  待确认/
    格式/
      文件名
```

示例：

```text
学习资料库/小学/三年级/数学/教材/人教版/义务教育教科书_数学三年级上册_33c8d495.pdf
学习资料库/8岁/未分年级/数学/四则混合运算/示例来源/四则混合运算练习题_ab12cd34.pdf
学习资料库/待确认/pdf/未知标题_09af31bc.pdf
```

状态：已创建第一版，支持 `learning-library-organize/v1` 输出、通用多格式路径、低置信度进入 `待确认/`；第一版以元数据和文件名启发式分类为主，尚未接入 OCR、字幕和全文内容分类。

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

状态：已创建第一版，支持 `learning-library-index-update/v1` 输出，默认维护资料库外部 `resources.json` 和 `duplicates.json`；第一版只记录重复，不自动删除或移动资料库文件。

## 统一候选资源格式草案

所有 source skill 应尽量输出如下结构，供 ranker 消费：

```json
{
  "source": "smartedu-resources",
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

- 分类置信度高于当前自动归档阈值：按分类路径归档。
- 低于当前自动归档阈值：进入 `待确认/` 或询问用户。
- 低于 0.60：只保留来源 ID 和原始文件，等待确认。

## 当前已完成

### SmartEdu 教材早期兼容适配资产

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

当前定位与限制：

- 它是早期为验证“教材候选 -> 下载 -> 整理”链路而创建的实现资产。
- 当前主要面向 SmartEdu `tchMaterial` PDF 教材。
- 外部任务路由应进入 `smartedu-resources`；后续将把可复用能力逐步迁入 `smartedu-resources` 的内部教材分支。

## 下一步计划

### P0：补齐基础契约

- [x] 为 `smartedu-textbooks` 增加标准候选资源输出格式。
- [x] 将 `--list-only` 输出调整为 ranker 可直接消费的结构。
- [x] 明确工作缓存目录和最终资料库目录的边界。
- [x] 为 `smartedu-textbooks` 增加 `--output`，并在下载候选中补充 `local_file`。

### P1：创建需求理解 skill

- [x] 创建 `learning-resource-flow` 总控编排 skill。
- [x] 为教材请求增加早期 SmartEdu 教材适配脚本到 analyzer/ranker 的脚本化测试链路。
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
- [x] 用离线真实格式 fixture 做 DOCX、PPTX、PNG、HTML 风险页样例测试。

### P3：创建资料库整理 skill

- [x] 创建 `learning-resource-downloader`。
- [x] 固化 `learning-resource-download/v1` 输出契约。
- [x] 实现用户选择编号到工作缓存下载的第一版脚本。
- [x] 创建 `learning-library-organizer`。
- [x] 固化 `learning-library-organize/v1` 输出契约。
- [x] 支持多格式目录结构。
- [x] 支持低置信度进入 `待确认/`。
- [x] 创建 `learning-library-index`。
- [x] 设计资料库外部索引格式。
- [x] 支持按 `sha256` 记录重复资源。
- [x] 阻止索引目录写入最终资料库内部。

### P4：扩展资源类型和来源

- [x] 创建 `web-learning-search` 通用网页候选搜索 skill。
- [x] 支持从网页搜索结果推断 PDF/DOC/PPT/图片/音频/视频/网页等候选格式。
- [x] 将 `web-learning-search` 从内置搜索改为接收 agent 通用搜索结果并标准化候选。
- [x] 创建 `local-library-search`，基于外部索引检索已有本地学习资料。
- [x] 创建 `resource-source-discovery`，从搜索结果中识别资源站候选并做来源级粗筛。
- [x] 创建 `web-resource-profiler`，对高价值资源站做结构分析。
- [x] 创建 `generic-web-source`，对简单资源站直接抽取候选资源。
- [x] 创建 `smartedu-resources`，解析 SmartEdu 全平台栏目和详情资源项候选。
- [x] 为 `smartedu-resources` 增加站点能力画像 `site-profile`。
- [x] 为 `learning-resource-flow` 增加 source-first 通用编排脚本，先查已优化站点 source，候选不足再接收 agent 通用搜索结果。
- [x] 将 `resource-source-discovery`、`web-resource-profiler`、`generic-web-source` 接入 source-first web fallback。
- [x] 将 `local-library-search` 接入 `learning-resource-flow`，支持先查本地资料库外部索引，本地候选不足时再进入外部来源。
- [x] 为 `learning-resource-flow` 增加用户确认后的脚本化闭环：selector 结果可通过 `--select` 继续进入 downloader、organizer 和 external index。
- [ ] 创建更多 source skills。

### P5：回归测试与质量保障

- [x] 创建离线 smoke test，覆盖核心 skill 链路。
- [ ] 为 intent 追问样例增加自动化断言。
- [x] 为 DOCX、PPTX、PNG、HTML 风险页增加 analyzer 样例。
- [x] 为 PDF 轻量文本、格式伪装登录页、音视频侧车字幕入口增加 analyzer 支持；图片 OCR 和自动转写仍待实现。
- [ ] 打包脚本化并自动检查敏感信息、缓存和资料库污染。

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

### 2026-06-05

- 创建 `learning-library-organizer` 第一版，负责将 downloader 的 `learning-resource-download/v1` 输出整理为最终资料库文件。
- 固化 `learning-library-organize/v1` 输出契约，归档摘要保存在工作目录或命令输出，不进入最终资料库。
- 实现 `scripts/organize_downloads.py`，支持复制或移动文件、规范命名、哈希短标识、冲突文件名自动追加序号。
- 采用通用资料库结构：`学段或适龄/年级或阶段/学习领域或学科/主题或资源类型/来源或版本/文件名`，不将资料类型和来源硬绑定。
- 实现低置信度资源进入 `待确认/格式/`，保证最终资料库只包含真实资源文件。
- 创建 `learning-library-index` 第一版，负责在最终资料库外部维护资源索引、去重记录和来源追踪。
- 固化 `learning-library-index-update/v1` 输出契约，默认维护 `.learning-resource-work/index/resources.json` 和 `duplicates.json`。
- 实现 `scripts/update_index.py`，支持新增、同路径更新、同哈希不同路径重复记录和 dry-run。
- 增加保护：索引目录或索引输出摘要不能位于最终资料库内部。
- 创建 `local-library-search` 第一版，基于 `resources.json` 检索本地已有学习资源，并输出 `learning-resource-candidate/v1` 标准候选。
- 实现 `scripts/search_local_library.py`，支持 query、task JSON、格式偏好、资源类型、主题、学科、学段/年级匹配和缺失文件标记。
- 将本地检索接入总控流程：如已有本地索引，先产生本地候选，再与其他来源候选一起进入 analyzer、ranker、selector。
- 创建 `scripts/run_smoke_tests.py` 离线回归脚本，覆盖通用搜索候选标准化、analyzer/ranker/selector、organizer、index、本地检索和索引目录保护。
- 创建 `resource-source-discovery` 第一版，负责从搜索结果或网页候选中识别已知来源、资源站、资源页、视频页、普通文章和风险下载页。
- 固化 `learning-resource-source-discovery/v1` 输出契约，区分 `sources` 与 `rejected_sources`，并输出 `next_action` 供后续 profiler 或 source skill 使用。
- 创建 `web-resource-profiler` 第一版，负责对高价值资源站做 HTML、资源直链、script、疑似 API、分页、详情页、登录限制和接入策略分析。
- 固化 `site-profile/v1` 输出契约，支持 `generic_extract`、`profile_deeper`、`dedicated_source_skill`、`keep_as_web_candidate`、`reject` 等策略。
- 创建 `generic-web-source` 第一版，负责从 `site-profile/v1` 或本地 HTML 中抽取 PDF、Office、图片、音频、视频和压缩包等资源直链候选。
- 固化 `generic-web-source` 的候选输出边界：`source_url` 使用资源直链，`raw.origin_page_url` 保留来源页面；不下载、不评分、不写资料库。
- 将 `generic-web-source` 接入 `learning-resource-flow` 和离线 smoke test，覆盖 `resource-source-discovery -> web-resource-profiler -> generic-web-source` 链路。
- 增强 `learning-resource-analyzer` 图片尺寸识别：在无 PIL 环境下通过 PNG/GIF/JPEG 文件头解析宽高。
- 扩展离线 smoke test 的多格式 analyzer 样例，自动构造 DOCX、PPTX、PNG、HTML 风险页并断言正文、幻灯片数、图片宽高和风险词。
- 分析 SmartEdu 当前首页和前端配置，确认平台栏目清单来自 `librarylist.json`，详情资源统一通过 `ti_items` 暴露视频、音频、PDF、图片、文档等文件项。
- 创建 `smartedu-resources` 第一版，支持 `smartedu-catalog-profile/v1` 栏目画像和 `learning-resource-candidate/v1` 详情候选输出。
- 修正 SmartEdu source 架构表述：教材本身属于 SmartEdu resources，`smartedu-resources` 是站点级总入口，`smartedu-textbooks` 只作为早期 `tchMaterial` 教材 PDF 兼容适配资产保留。
- 将 `smartedu-resources` 接入 `learning-resource-flow` 和 intent 任务契约；遇到教材 `tchMaterial` 时仍统一路由到 `smartedu-resources`，必要时由其内部复用或迁移早期教材适配脚本。

### 2026-06-06

- 明确站点级 source 设计原则：每个资源站点 skill 应掌控站内所有可识别资源类型，不能因为测试阶段先跑通教材就把教材暴露成独立资源站来源。
- 调整 SmartEdu 路由：`basic.smartedu.cn`、`/tchMaterial`、课程、课件、习题、试卷、视频等站内资源统一归属 `smartedu-resources`。
- 更新 SmartEdu 栏目画像：教材栏目保留 `resource_family=教材` 和 `internal_adapter=tchMaterial`，但 `known_skill=smartedu-resources`。
- 将 `smartedu-textbooks` 标记为早期兼容适配层，后续只作为 `smartedu-resources` 内部实现资产复用或迁移。
- 为 `smartedu-resources` 增加 `textbook-candidates` 子命令，外部可直接通过站点级 skill 获取 SmartEdu 教材候选；内部暂时复用早期教材适配脚本，候选 `source` 统一为 `smartedu-resources`。
- 为 `smartedu-resources` 增加授权上下文注入能力，支持 `SMARTEDU_ACCESS_TOKEN`、`SMARTEDU_COOKIE`、`SMARTEDU_AUTHORIZATION`、`SMARTEDU_HEADERS` 以及临时 `--cookie`、`--header`；输出只记录 `auth_context=true/false`，不写入凭据原文。
- 为 `smartedu-resources search-resources` 增加 `--fetch-details`、`--detail-dir` 和 `--offline-details-only`，支持从搜索候选继续追踪 SmartEdu 详情 JSON，并把详情中的 `ti_items` 展开为真实文件项候选；详情缺失时保留搜索候选并记录失败原因。
- 增强 `learning-resource-downloader` 对 SmartEdu 文件项候选的支持：默认跳过 `requires_auth=true` 资源；显式 `--allow-auth` 且存在授权上下文时，尝试 `source_url` 和 `candidate.raw.url_candidates`；下载输出只记录 `auth_context=true/false`，不泄露 token、cookie 或 header 原文。
- 为 `learning-resource-downloader` 增加 `--probe-only`，支持下载前按顺序探测 `source_url` 和 `candidate.raw.url_candidates` 的可访问性、HTTP 状态、内容类型和长度；探测模式不保存文件，适合 SmartEdu 私有/公共候选 URL 的下载前筛选。
- 受当前沙箱限制，离线回归不能启动本地 HTTP 服务做成功下载样例；已保留默认跳过、授权探测、URL fallback 尝试和敏感信息不泄露测试。真实成功下载需在有网络/账号态环境中用 `SMARTEDU_ACCESS_TOKEN` 注入后执行 `search-resources --fetch-details`、selector、downloader `--probe-only` 和正式下载。

### 2026-06-08

- 为 `smartedu-resources` 增加 `site-profile` 子命令，输出 `learning-resource-source-profile/v1` 站点能力画像，包含资源类型覆盖、格式覆盖、可用命令、授权策略、栏目摘要和路由策略。
- 为 `smartedu-resources` 增加 `route-map` 子命令，输出 `smartedu-route-map/v1` 栏目路由图，把 `librarylist.json` 中的栏目转为页面 URL、搜索 tab、详情模板和扫描策略。
- 为 `smartedu-resources` 增加 `page-profile` 子命令，输出 `smartedu-page-profile/v1` 页面画像，从 SmartEdu 页面 HTML/JS 中抽取 API、详情 ID、资源链接和下一步动作线索。
- 为 `smartedu-resources` 增加 `scan-catalog` 子命令，输出 `smartedu-catalog-scan/v1`，可按 route-map 中的栏目路由扫描候选；第一版支持离线搜索响应归一化、在线搜索接口联调入口和可选详情追踪。
- 为 `smartedu-resources` 增加 `scan-site` 子命令，输出 `smartedu-site-scan/v1`，可基于 route-map 批量扫描多个栏目、汇总候选、去重并记录失败 route。
- 真实环境联调 SmartEdu 公开栏目配置：`route-map` 可联网读取官方 `librarylist.json`，真实数据中共 147 个栏目项，去重后得到 133 条唯一 route，包含 1 条教材内部适配分支和 132 条搜索到详情分支。
- 修正 SmartEdu route-map 重复栏目问题，新增 route 去重统计 `duplicates_removed`。
- 修正 `page-profile` 对前端根节点 ID 的误判，不再把 `id="root-x-edu-web"` 识别为详情资源 ID。
- 为 `page-profile` 增加 `--fetch-scripts` 和 `--script-limit`，可选择抓取页面引用的 JS 文件并一起抽取接口线索；默认关闭，避免普通调用额外联网。
- 真实环境联调 SmartEdu 搜索网关：未登录和仅 access token 注入时，`resource-gateway.ykt.eduyun.cn` 搜索接口均返回 403；后续真实扫描需要完整 cookie、Authorization 或浏览器上下文。
- 将 SmartEdu 能力画像接入离线 smoke test，验证授权上下文只输出 `auth_context=true/false`，不泄露 header、token 或 cookie 原文。
- 为 `learning-resource-flow` 新增 `scripts/run_resource_flow.py`，支持接收 `learning-resource-intent/v1` 结构化意图，先调用已优化站点 source，再按候选阈值决定是否进入通用网络搜索分支。
- 新增 source-first 离线回归用例：SmartEdu 样例候选不足时，流程自动接收 `web-learning-search` 标准化后的 agent 搜索结果，并继续进入 analyzer、ranker、selector。
- 将 source-first 的 web fallback 后半段接入完整链路：`web-learning-search -> resource-source-discovery -> web-resource-profiler -> generic-web-source`；流程会保留 `web-candidates.json`、`source-discovery.json`、`site-profile.json`、`generic-candidates.json` 等工作文件用于调试。
- 更新 `learning-resource-flow` 主说明、`source-policy.md` 和 `flow-cases.md`：标准流程从“教材类/主题类”分支改为“意图解构 -> 已优化 source 优先 -> 网络搜索补充 -> 统一分析评分选择”。
- 将 `local-library-search` 接入 `learning-resource-flow`，默认先查 `.learning-resource-work/index/resources.json`；本地候选达到阈值时可直接进入 analyzer/ranker/selector，本地不足再查已优化 source 和 web fallback。
- 为 `learning-resource-flow` 增加 `--select` 后处理链路，用户确认候选编号后可继续执行 `learning-resource-downloader -> learning-resource-analyzer -> learning-library-organizer -> learning-library-index`，下载后先复查真实文件再归档，并把下载、归档、索引摘要写回 `post_selection`。
- 增强 `learning-resource-analyzer` 的通用资源证据：轻量提取 PDF 页数和文本样本，识别声明格式与实际内容不一致的伪装资源，标记登录/权限/会员页风险，音视频支持同名 `.srt/.vtt/.lrc/.txt` 侧车文本。
- 增强 `learning-resource-ranker` 对内容证据和用户偏好的消费：评分中加入 `content_evidence` 和 `preference_fit`，对缺少内容证据、登录限制、格式伪装、可打印/听赏/视频场景做更明确的加权或降权。
- 扩展离线 smoke test：新增本地资料库优先 flow 用例、基于本机 HTTP 服务的 `flow --select` 下载归档索引用例，以及声明为 PDF 的 HTML 登录页识别断言。
