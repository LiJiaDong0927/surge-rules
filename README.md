# surge-rules

自用 Surge 规则及维护工具。仓库只保存分流名单、适配脚本和说明，不保存完整代理配置或订阅凭据。

| 内容 | 用途 |
| --- | --- |
| [ChinaDomain.local.list](ChinaDomain.local.list) | 现有国内网站域名名单；本次保留原文件及地址 |
| [One Exit for Surge](one-exit-surge/README.md) | 将 One Exit 目标交给现有手动选择组，并保留原有直连例外 |
| [One Exit 名单](one-exit-surge/one-exit-targets.list) | 可维护的源名单，不包含代理策略或 DNS 设置 |
| [可选 Module](one-exit-surge/one-exit-targets.sgmodule) | 从名单生成的数据模块；不能单独完成分流 |

## Raw 地址

- [国内域名名单](https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/ChinaDomain.local.list)
- [One Exit 名单](https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/one-exit-surge/one-exit-targets.list)
- [One Exit 可选 Module](https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/one-exit-surge/one-exit-targets.sgmodule)

当前已安装的 One Exit 使用本地内嵌名单。仅修改 GitHub 不会改变这份生效配置；同步方法见 [维护说明](one-exit-surge/README.md#维护和更新)。本仓库不自动抓取上游，避免未经审查的变更影响分流。

完整配置、`.private/`、订阅链接和账号密码仅保留在本机。
