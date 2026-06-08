# 测试用例

## 用例 1：站点能力画像

输入 `sample-librarylist.json`。

期望：

- 输出 `learning-resource-source-profile/v1`。
- 说明本来源是普通候选来源，不与主题、类型或格式硬绑定。
- 能列出站内资源类型、格式覆盖、可用命令和授权策略。
- 如果传入 header、cookie 或 token，只能输出 `auth_context=true`，不得泄露原文。

## 用例 2：栏目画像

输入 `sample-librarylist.json`。

期望：

- 输出 `smartedu-catalog-profile/v1`。
- 能识别课程教学、备课资源、精品课、实验教学、家庭教育。
- 教材栏目应仍标记为 `known_skill=smartedu-resources`，并通过 `resource_family=教材`、`internal_adapter=tchMaterial` 表示站内教材资源分支。

## 用例 3：详情资源项解析

输入 `sample-detail.json`。

期望：

- 输出 `learning-resource-candidate/v1`。
- 生成视频、PDF、图片候选。
- `custom_properties.identification=true` 的候选标记 `requires_auth=true`。
- 候选保留 `raw.smartedu_item`。

## 用例 4：与 analyzer/ranker 串联

`candidates-from-detail` 输出应能直接交给 `learning-resource-analyzer` 和 `learning-resource-ranker`。

## 用例 5：不下载

脚本不应下载 m3u8、PDF、图片或其他真实文件；只输出候选和元数据。
