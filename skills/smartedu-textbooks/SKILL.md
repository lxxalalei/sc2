---
name: smartedu-textbooks
description: 从国家中小学智慧教育平台 / SmartEdu 查找、下载并整理中国中小学教材 PDF。当用户要求查找、获取、爬取、下载或建立教材/电子教材本地资料库时使用，例如"帮我查找小学三年级教材"、"下载人教版小学数学上册"或"整理一份本地教材资料库"。
---

# SmartEdu 教材下载

## 核心规则

使用 `scripts/fetch_textbooks.py` 作为入口点。不要直接调用爬虫核心进行面向用户的下载，因为包装脚本会在工作缓存中保留元数据，并确保最终资料库中只包含 PDF 文件。

最终资料库目录必须只包含已下载的教材 PDF 文件。JSON、清单、日志和临时文件必须保留在工作目录下。

## 需求理解与澄清

先用模型能力理解用户自然语言，不要把 skill 当成简单下载脚本。

下载前必须判断需求是否足够明确。关键槽位：

- 学段：小学/初中/高中
- 年级：如 三年级、七年级、高一
- 学科：如 数学、语文、英语
- 版本/出版社：如 人教版、统编版、北师大版
- 册次：如 上册、下册、全一册

最小可下载条件通常是：学段 + 年级 + 学科 + 版本 + 册次。若缺少其中多个关键槽位，不要直接下载；先向用户追问。

追问要短，一次优先问最能缩小范围的 1-3 个问题：

- 用户说“帮我下载数学教材”：问“需要哪个学段/年级、哪个版本、上册还是下册？”
- 用户说“帮我找小学三年级教材”：问“要哪个学科和版本？是否上下册都要？”
- 用户说“下载小学三年级人教版数学”：问“要上册、下册，还是都下载？”
- 用户说“下载人教版小学三年级数学上册”：需求明确，可以执行下载。

如果用户明确表示“全部/都要”，可以省略对应槽位。例如“下载小学三年级人教版全部教材”可以使用 `--stage 小学 --grade 三年级 --version 人教版`，但下载前应告知匹配数量或先 `--list-only` 展示候选。

模糊需求处理流程：

1. 从话语中抽取已有槽位。
2. 对缺失槽位做判断：缺学段/年级/学科/版本/册次时，通常先追问。
3. 若用户要求先看看有哪些，运行 `--list-only` 展示候选，不需要 token。
4. 用户确认后再下载。

## 输入映射

将用户用语映射到脚本参数：

- `小学/初中/高中` -> `--stage`
- `一年级` 至 `九年级`、`高一`、`高二`、`高三` -> `--grade`
- `语文/数学/英语/道德与法治/科学/音乐/美术/体育与健康` -> `--subject`
- `人教版/统编版/北师大版/苏教版/冀教版` 等出版社/版本用语 -> `--version`
- `上册/下册/全一册/必修/选择性必修` -> `--volume`
- 其他标题关键词 -> `--query`

如果用户只说"小学三年级教材"，不要直接下载；先询问学科、版本和册次，或用 `--list-only --stage 小学 --grade 三年级` 展示候选。

## 目录设计

使用以下资料库布局：

```text
教材资料库/
  学段/
    年级/
      学科/
        版本/
          册次/
            教材标题_资源ID前8位.pdf
```

示例：

```text
教材资料库/小学/三年级/数学/人教版/上册/义务教育教科书 · 数学三年级上册_33c8d495.pdf
教材资料库/小学/三年级/英语/人教版（PEP）（主编：吴欣）/下册/义务教育教科书·英语 三年级 下册_9eb54ff2.pdf
```

当用户要求特定输出位置时，使用 `--library-dir`。否则在当前工作目录使用 `教材资料库`。

## Token 处理

PDF 下载需要 SmartEdu 访问令牌。优先使用环境变量：

```bash
SMARTEDU_ACCESS_TOKEN='...' python3 scripts/fetch_textbooks.py --stage 小学 --grade 三年级
```

切勿将令牌写入 skill 文件、源代码、README 文件或最终资料库。如果对话中提供了令牌，请仅作为正在运行的命令的环境变量传递。

## 工作流程

1. 解析用户请求为筛选条件。
2. 判断关键槽位是否足够明确；不明确时追问，不要直接下载。
3. 若需要给用户候选，运行 `scripts/fetch_textbooks.py --list-only ...`。
4. 如果用户未提供令牌且未设置 `SMARTEDU_ACCESS_TOKEN`，请索要令牌或说明 PDF 下载需要令牌。
5. 如果请求范围较广，验证时先使用 `--probe-only` 或 `--limit`，确认后再运行完整下载。
6. 报告匹配的教材数量、下载数量和最终资料库路径。
7. 不要将缓存文件作为面向用户的结果展示。

## 命令

探测可用性而不保存 PDF：

```bash
SMARTEDU_ACCESS_TOKEN='...' python3 scripts/fetch_textbooks.py \
  --stage 小学 --grade 三年级 --version 人教版 --probe-only
```

列出候选教材，不需要 token：

```bash
python3 scripts/fetch_textbooks.py \
  --stage 小学 --grade 三年级 --subject 数学 --list-only
```

下载匹配的 PDF 到默认资料库：

```bash
SMARTEDU_ACCESS_TOKEN='...' python3 scripts/fetch_textbooks.py \
  --stage 小学 --grade 三年级 --version 人教版
```

下载到特定资料库目录：

```bash
SMARTEDU_ACCESS_TOKEN='...' python3 scripts/fetch_textbooks.py \
  --stage 小学 --grade 三年级 --subject 数学 \
  --library-dir /path/to/教材资料库
```

强制刷新 SmartEdu 索引同步：

```bash
SMARTEDU_ACCESS_TOKEN='...' python3 scripts/fetch_textbooks.py \
  --stage 小学 --grade 三年级 --sync
```

## 输出约定

包装脚本输出 JSON 摘要，包含：

- `matched`: 匹配记录数
- `downloaded`: 成功 PDF 下载数或成功探测数
- `library_dir`: 仅含 PDF 的最终资料库路径
- `files`: 非探测模式时的最终 PDF 路径
- `failures`: 失败记录及原因

使用此摘要作为最终回复。
