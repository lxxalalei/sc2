# 学习资源下载输出契约

## 顶层结构

```json
{
  "download_schema": "learning-resource-download/v1",
  "status": "completed | partial | failed",
  "requested": [],
  "downloaded_files": [],
  "skipped": [],
  "failures": [],
  "work_dir": ""
}
```

## downloaded_files

```json
{
  "option_id": "A",
  "title": "",
  "source_url": "",
  "local_file": "",
  "format": "pdf",
  "resource_type": "",
  "size": 0,
  "sha256": "",
  "content_type": "",
  "candidate": {}
}
```

## skipped

```json
{
  "option_id": "B",
  "title": "",
  "reason": "需要登录或授权访问",
  "candidate": {}
}
```

## failures

```json
{
  "option_id": "C",
  "title": "",
  "source_url": "",
  "error": "",
  "candidate": {}
}
```

## 状态规则

- `completed`：所有请求项都成功下载。
- `partial`：部分成功，部分跳过或失败。
- `failed`：没有任何文件成功下载。
