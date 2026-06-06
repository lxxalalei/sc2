# 学习资源下载输出契约

## 顶层结构

```json
{
  "download_schema": "learning-resource-download/v1",
  "status": "completed | partial | failed",
  "requested": [],
  "downloaded_files": [],
  "probed": [],
  "skipped": [],
  "failures": [],
  "work_dir": "",
  "auth_context": false,
  "probe_only": false
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

## probed

`--probe-only` 模式下输出 URL 探测结果，不保存文件：

```json
{
  "option_id": "A",
  "title": "",
  "source_url": "",
  "format": "pdf",
  "resource_type": "",
  "accessible": true,
  "url_results": [
    {
      "url": "",
      "ok": true,
      "status": 200,
      "method": "HEAD",
      "content_type": "application/pdf",
      "content_length": 1024
    }
  ],
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

## 授权规则

- `requires_auth=true` 的候选默认进入 `skipped`。
- 只有显式传入 `--allow-auth` 且存在授权上下文时，才尝试下载授权资源。
- SmartEdu 候选可包含 `candidate.raw.url_candidates`，下载器应按顺序尝试这些 URL。
- `--probe-only` 只探测 `source_url` 和 `candidate.raw.url_candidates`，不写文件。
- 输出可包含 `auth_context=true/false`，但不得包含 token、cookie、authorization 或自定义 header 原文。
