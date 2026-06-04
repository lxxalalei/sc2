# 学习资源选择测试样例

## 样例 1：官方教材候选

输入：

- 两个 `high` 官方教材候选。

期望：

- 输出 A、B 两个选项。
- 明确提示来源为国家中小学智慧教育平台。
- 如果 `requires_auth=true`，提示需要登录或授权访问。

## 样例 2：练习题和无关视频

输入：

- 一个 `high` PDF 练习题。
- 一个 `low` 无关视频。
- 一个 `reject` 下载器风险页面。

期望：

- 只展示 PDF 练习题。
- 无关视频和下载器风险进入 `hidden_options`。

## 样例 3：没有合适资源

输入：

- 全部候选都是 `reject`。

期望：

- `status=no_suitable_options`
- `options=[]`
- `user_message` 建议用户补充需求或换关键词重新搜索。
