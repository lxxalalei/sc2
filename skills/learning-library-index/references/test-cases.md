# 学习资料库索引测试样例

## 样例 1：新增资源

输入：

- organizer 输出 1 个 `organized_files[]`。
- `sha256` 不在现有索引中。

期望：

- `resources.json` 新增 1 条。
- 输出 `created=1`。
- 最终资料库目录不出现索引文件。

## 样例 2：同一路径更新

输入：

- 相同 `sha256`、相同 `library_file` 已存在。

期望：

- 更新该资源元数据和 `updated_at`。
- 输出 `updated=1`。

## 样例 3：重复文件

输入：

- 相同 `sha256`、不同 `library_file`。

期望：

- 不删除任何文件。
- `duplicates.json` 增加重复记录。
- 输出 `duplicates`。

## 样例 4：索引目录放进资料库

输入：

- `--index-dir 学习资料库/index`。

期望：

- 拒绝执行。
- 输出错误或返回失败，避免污染最终资料库。
