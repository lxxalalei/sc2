# 测试用例

## 用例 1：从 site-profile 抽取 PDF/DOCX

输入：

- `site-profile/v1`
- `crawl_strategy=generic_extract`
- `resource_links` 包含 PDF 和 DOCX

期望：

- 输出 `learning-resource-candidate/v1`
- 至少生成 2 个候选
- PDF 候选 `format=pdf`
- 候选 `raw.origin_page_url` 指向原资源站页面

## 用例 2：跳过非通用抽取画像

输入：

- `crawl_strategy=dedicated_source_skill`
- 有 API 线索但无资源直链

期望：

- 不生成候选
- `summary.skipped` 大于 0

## 用例 3：登录或付费提示

输入：

- 画像 `auth_hints` 包含登录、会员或付费

期望：

- 候选 `requires_auth=true`
- `raw.warnings` 记录可能存在访问限制

## 用例 4：HTML 本地调试

输入：

- `--url`
- `--html-file`

期望：

- 从 `<a href>` 中抽取文件直链
- 相对路径转换为绝对 URL
