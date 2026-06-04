# SmartEdu 官方教材模块说明

本模块用于抓取 `https://basic.smartedu.cn/tchMaterial` 的教材数据。页面本身是前端应用，教材列表来自平台静态 JSON：

- `zxx/ndrs/resources/tch_material/version/data_version.json`
- `zxx/ndrs/resources/tch_material/part_*.json`
- 单本详情：`zxx/ndrv2/resources/tch_material/details/{id}.json`

## 模块入口

推荐通过 skill 包装脚本使用：

```bash
python3 skills/smartedu-textbooks/scripts/fetch_textbooks.py --help
```

列出标准候选并写入文件：

```bash
python3 skills/smartedu-textbooks/scripts/fetch_textbooks.py \
  --stage 小学 --grade 三年级 --subject 数学 --version 人教版 \
  --list-only -o /tmp/smartedu-candidates.json
```

候选可继续交给详情分析和评分：

```bash
python3 skills/learning-resource-analyzer/scripts/analyze_candidates.py \
  /tmp/smartedu-candidates.json -o /tmp/smartedu-analyzed.json

python3 skills/learning-resource-ranker/scripts/rank_candidates.py \
  /tmp/smartedu-analyzed.json
```

下载成功后的 JSON 摘要会包含 `candidate_schema`、`candidates` 和 `files`；下载候选中的 `local_file` 指向最终资料库里的 PDF，可继续用于本地 PDF 分析。

也可以直接使用根目录爬虫脚本进行调试：

```bash
python3 smartedu_tch_material.py --help
```

## 常用命令

同步全量教材索引：

```bash
python3 smartedu_tch_material.py sync
```

按条件检索：

```bash
python3 smartedu_tch_material.py list --stage 小学 --subject 数学 --grade 一年级
```

导出 CSV：

```bash
python3 smartedu_tch_material.py export-csv -o data/textbooks.csv
```

补全 PDF 源文件元数据：

```bash
python3 smartedu_tch_material.py pdf-meta --query 道德与法治 --limit 5
```

使用登录 token 下载 PDF：

```bash
SMARTEDU_ACCESS_TOKEN='你的 access token' \
python3 smartedu_tch_material.py download-pdfs --stage 小学 --version 人教版 --grade 三年级 -o downloads/pdfs
```

只测试资源是否可访问，不保存完整 PDF：

```bash
SMARTEDU_ACCESS_TOKEN='你的 access token' \
python3 smartedu_tch_material.py download-pdfs --stage 小学 --version 人教版 --grade 三年级 --probe-only
```

下载预览图：

```bash
python3 smartedu_tch_material.py download-previews --query 道德与法治 --limit 1 --pages 3
```

## 输出文件

以下输出属于工作缓存或调试产物，不应进入最终资料库：

- `data/version.json`：版本入口数据。
- `data/tags.json`：教材标签树。
- `data/textbooks.raw.json`：平台原始教材列表。
- `data/textbooks.json`：规范化后的教材列表。
- `data/textbooks.with_pdf_meta.json`：执行 `pdf-meta` 后生成，包含 `pdf_items` 和 `pdf_urls`。
- `data/details/{id}.json`：单本教材详情缓存。
- `downloads/previews/`：预览图下载目录。
- `downloads/pdfs/manifest.json`：PDF 下载结果清单。

最终资料库只保留实际教材文件。

## 说明

平台详情接口会返回 PDF 源文件的 `ti_items`，但源文件 URL 通常位于受保护资源域，未带登录态或鉴权参数时直连可能返回 403。当前程序会保存候选 PDF URL 和源文件元数据，方便后续在 skill 中接入登录态、鉴权头或资源解析逻辑。

预览图是公开转码图片，通常可以直接下载。
