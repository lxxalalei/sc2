# 学习资源分析测试样例

## 样例 1：PDF 练习题候选

输入候选：

```json
{
  "title": "8岁四则混合运算可打印练习题 PDF",
  "format": "pdf",
  "source_url": "https://example.edu.cn/math.pdf"
}
```

期望：

- `analysis_type=document`
- `detected_format=pdf`
- 未启用远程抓取时提示 `远程抓取未启用`
- 不虚构页数或正文

## 样例 2：本地 HTML 网页

输入候选带 `local_file`：

```json
{
  "title": "恐龙百科",
  "format": "html",
  "local_file": "sample.html"
}
```

期望：

- 提取网页标题和正文样本
- 识别百科、恐龙等关键词
- `analysis_confidence` 高于只有 URL 的候选

## 样例 3：PPT 课件

输入本地 `.pptx`：

期望：

- `analysis_type=document`
- 提取幻灯片 XML 中的文本样本
- `signals.slide_count` 有值

## 样例 4：图片

输入本地 `.png`：

期望：

- `analysis_type=image`
- 提取宽高；环境没有图像库时，应通过 PNG/GIF/JPEG 文件头回退解析
- 不做 OCR 虚构文字

## 样例 5：风险网页

标题或正文包含：

```text
高速下载器 免费破解 成人
```

期望：

- `warnings` 包含下载器、破解、成人化风险
- 后续 ranker 应据此降权
