# surge-rules

自用 Surge 规则及维护工具。仓库只保存分流名单、适配脚本和说明，不保存完整代理配置或订阅凭据。

| 内容 | 用途 |
| --- | --- |
| [ChinaDomain.local.list](ChinaDomain.local.list) | 现有国内网站域名名单；本次保留原文件及地址 |
| [One Exit for Surge](one-exit-surge/README.md) | 将 One Exit 目标交给现有手动选择组，并保留原有直连例外 |
| [One Exit 名单](one-exit-surge/one-exit-targets.list) | 可维护的源名单，不包含代理策略或 DNS 设置 |
| [可选 Module](one-exit-surge/one-exit-targets.sgmodule) | 从名单生成的数据模块；不能单独完成分流 |
| [Apple News 名单](AppleNews.list) | News 进程、新闻域名、地区检测和首次加载接口；策略由主配置指定 |

## Raw 地址

- [国内域名名单](https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/ChinaDomain.local.list)
- [One Exit 名单](https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/one-exit-surge/one-exit-targets.list)
- [One Exit 可选 Module](https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/one-exit-surge/one-exit-targets.sgmodule)
- [Apple News 名单](https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/AppleNews.list)

当前本机 One Exit 已改用本仓库的远程名单，设置为每小时检查更新（Surge 运行且联网时）。提交 `one-exit-surge/one-exit-targets.list` 后，可等待自动更新，或在 Surge 外部资源中手动刷新该名单。接入、验证和回滚见 [维护说明](one-exit-surge/README.md#维护和更新)。本仓库不自动抓取上游，避免未经审查的变更影响分流。

## Apple News

在现有 `[Rule]` 的自定义规则区域加入以下一行，放在 Apple 通用分流和 One Exit 规则之前。已有的 Apple News 内嵌规则可用这一行替换，避免重复维护：

```ini
RULE-SET,https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/AppleNews.list,♻️ 手动切换,update-interval=3600
```

策略组选择英国、美国、加拿大或澳大利亚节点。Surge 运行且联网时每小时检查名单更新，也可以在外部资源列表中手动刷新；GitHub Raw 缓存可能造成延迟。

名单包含 12 条匹配条件，不含策略、节点或订阅凭据。`PROCESS-NAME,News` 仅 Surge Mac 有效，iOS 会忽略该条。`gspe1-ssl.ls.apple.com` 和 `gateway.icloud.com` 是共享 Apple 接口，相关请求也会跟随所选节点，并可能影响其他 Apple 服务的地区判断。这些规则负责分流，不能保证通过所有地区检查；排查步骤见 [iRingo News 指引](https://nsringo.github.io/guide/apple-news)。

完整配置、`.private/`、订阅链接和账号密码仅保留在本机。
