# 学习资源下载测试样例

## 样例 1：PDF 直链

输入：

- selector 选项 A，`downloadable=true`，`format=pdf`，不需要授权。

期望：

- 下载到工作缓存目录。
- 输出 `local_file`、`sha256`、`size`。
- 不移动到最终资料库。

## 样例 2：需要登录资源

输入：

- selector 选项 A，`requires_auth=true`。

期望：

- 不强行下载。
- 写入 `skipped`。
- 原因说明需要授权或专用下载器。

## 样例 3：网页候选

输入：

- `format=html` 或 `downloadable=false` 但有 `source_url`。

期望：

- 可保存网页快照到工作缓存。
- 后续由 analyzer/organizer 继续处理。

## 样例 4：用户选择不存在

输入：

- 用户选择 `Z`。

期望：

- 输出失败或跳过，说明选择编号不存在。
