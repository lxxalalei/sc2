# 学习资料库索引更新输出契约

## 顶层结构

```json
{
  "index_schema": "learning-library-index-update/v1",
  "status": "completed | partial | failed",
  "index_dir": "",
  "resources_file": "",
  "duplicates_file": "",
  "created": 0,
  "updated": 0,
  "duplicates": [],
  "failures": [],
  "summary": {
    "input_files": 0,
    "total_indexed": 0,
    "created": 0,
    "updated": 0,
    "duplicates": 0,
    "failed": 0
  }
}
```

## resources.json

```json
{
  "index_schema": "learning-library-index/v1",
  "updated_at": "",
  "resources": [
    {
      "resource_key": "",
      "title": "",
      "library_file": "",
      "format": "pdf",
      "resource_type": "习题",
      "classification": {
        "stage_or_age": "8岁",
        "grade_or_phase": "未分年级",
        "domain_or_subject": "数学",
        "topic_or_type": "四则混合运算",
        "source_or_version": "示例来源"
      },
      "classification_confidence": 0.78,
      "needs_review": false,
      "source_url": "",
      "sha256": "",
      "dedupe_confidence": "high",
      "created_at": "",
      "updated_at": ""
    }
  ]
}
```

## duplicates.json

```json
{
  "duplicate_schema": "learning-library-duplicates/v1",
  "updated_at": "",
  "duplicates": [
    {
      "resource_key": "",
      "existing_file": "",
      "incoming_file": "",
      "title": "",
      "detected_at": "",
      "reason": "sha256 相同但资料库路径不同"
    }
  ]
}
```

## failures

```json
{
  "title": "",
  "library_file": "",
  "error": "资料库文件不存在"
}
```
