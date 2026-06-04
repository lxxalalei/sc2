# 学习资源分析输出契约

## 顶层结构

```json
{
  "analysis_schema": "learning-resource-analysis/v1",
  "candidate_schema": "learning-resource-candidate/v1",
  "source_candidate_count": 0,
  "analyzed_count": 0,
  "candidates": []
}
```

## 候选增强字段

分析结果写入候选的 `raw.analysis`，避免覆盖 source skill 已经给出的事实字段。

```json
{
  "raw": {
    "analysis": {
      "analyzed": true,
      "analysis_type": "document | webpage | image | audio | video | unknown",
      "detected_format": "pdf",
      "signals": {
        "file_size": 1024,
        "page_count": 12,
        "slide_count": null,
        "duration_seconds": null,
        "width": null,
        "height": null,
        "text_length": 0
      },
      "text_sample": "",
      "keywords": [],
      "warnings": [],
      "analysis_confidence": 0.0
    }
  }
}
```

## analysis_type

- `document`：PDF、DOC/DOCX、PPT/PPTX、TXT。
- `webpage`：HTML 网页。
- `image`：JPG、PNG、WEBP、GIF 等图片。
- `audio`：MP3、WAV、M4A 等音频。
- `video`：MP4、MOV、AVI 等视频。
- `unknown`：无法判断或暂不支持。

## warnings

常见风险：

- `文件不存在`
- `远程抓取未启用`
- `无法解析文本`
- `疑似下载器或广告页面`
- `可能需要登录或付费`
- `疑似成人化内容`
- `文件过小，可能不是完整资源`

## confidence

`analysis_confidence` 只表示分析证据充分程度：

- 0.80-1.00：成功解析出较多元数据或文本。
- 0.50-0.79：只有标题、摘要、文件大小等部分证据。
- 0.20-0.49：只知道格式或 URL。
- 0.00-0.19：几乎无法分析。
