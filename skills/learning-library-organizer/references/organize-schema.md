# 学习资料库归档输出契约

## 顶层结构

```json
{
  "organize_schema": "learning-library-organize/v1",
  "status": "completed | partial | failed",
  "library_dir": "",
  "organized_files": [],
  "failures": [],
  "summary": {
    "input_files": 0,
    "organized": 0,
    "failed": 0,
    "needs_review": 0
  }
}
```

## organized_files

```json
{
  "option_id": "A",
  "title": "",
  "source_url": "",
  "original_file": "",
  "library_file": "",
  "format": "pdf",
  "resource_type": "教材",
  "classification": {
    "stage_or_age": "小学",
    "grade_or_phase": "三年级",
    "domain_or_subject": "数学",
    "topic_or_type": "教材",
    "source_or_version": "人教版"
  },
  "classification_confidence": 0.82,
  "needs_review": false,
  "sha256": ""
}
```

## failures

```json
{
  "option_id": "B",
  "title": "",
  "local_file": "",
  "error": "文件不存在"
}
```

## 状态规则

- `completed`：所有可处理文件均已归档。
- `partial`：部分文件归档成功，部分失败。
- `failed`：没有任何文件归档成功。
