# One Exit for Surge

将 [wquguru/one-exit](https://github.com/wquguru/one-exit) 的目标名单移植到 Surge，统一使用现有的 **♻️ 手动切换** 策略组。切换该组节点后，新连接跟随新选择；已有连接可能继续使用旧连接。

本版本保留现有直连分流及 DNS 设置，不添加住宅代理，也不加入上游针对住宅代理故障的 IPv6 拒绝规则。它不能把普通节点变成固定住宅 IP。

## 文件与要求

| 文件 | 用途 |
| --- | --- |
| `one-exit-targets.list` | 唯一的源名单，无策略列 |
| `build_module.py` | 检查源名单并生成对应 Module；仅使用 Python 标准库 |
| `one-exit-targets.sgmodule` | 可选的数据模块，只定义 `[Ruleset OneExitTargets]` |
| `integrate.py` | 在本机备份、检查、集成和回滚配置；不上传配置 |

本机集成脚本要求 **Surge Mac 6.10+、Python 3.9+**。指定配置必须是 Surge 当前正在运行的同一份配置，且存在名为「♻️ 手动切换」的策略组；该组需已选择实际代理。脚本面向此配置结构，并非通用配置转换器。复杂逻辑或脚本规则会要求人工处理。

名单型 Module 要求 **Surge Mac 6.10+ / iOS 5.23+**。它本身没有分流规则或 DNS 设置，需要主配置绑定策略；不能单独安装后就认为出口已统一。已使用内嵌名单时，不要同时启用同名 Module。

## 当前内嵌方式

集成脚本在已有 `RULE-SET,LAN,DIRECT,no-resolve` 之后加入：

```ini
AND,((RULE-SET,OneExitTargets,no-resolve),(NOT,((RULE-SET,OneExitKeepDirect,no-resolve)))),♻️ 手动切换
```

同时在主配置末尾加入两个规则集：

- `OneExitTargets`：本地内嵌的目标名单，无远程下载依赖。
- `OneExitKeepDirect`：从原配置中当前选择 DIRECT 的规则提取条件，保留国内网站、视频、游戏和局域网等原有例外。

与直连例外重叠的目标会跳过新规则，继续按原配置顺序匹配。因此，某域名若原本先匹配其它代理规则，仍由原规则处理。若以后改变其它策略组的选择，需重新检查直连保护范围；保护名单不会自动随组选择变化。

原 `[General]`、DNS 和原有规则内容、顺序保持不变。所有新增 IP、GEOIP、嵌套 RULE-SET 均使用 `no-resolve`，避免新规则主动触发解析；这不代表全系统所有 DNS/WebRTC 流量都已被检查。

## 首次集成与回滚

已集成的配置不需要再次运行 `prepare`。首次使用时，进入此目录，确认配置名和策略组符合要求，再执行：

```bash
python3 integrate.py prepare --profile "$HOME/Library/Application Support/Surge/Profiles/TAG.conf"
python3 integrate.py apply
```

`TAG.conf` 只是配置名示例，应替换为当前运行的配置。脚本在本目录的 `.private/` 中生成原始备份、候选配置和状态，并调用 Surge 原生校验；只有校验通过后才可应用。应用会检查原文件和策略组选择未变化，然后重新载入 Surge。

回滚必须在**最初执行集成的同一个本机目录**中运行，因为新 clone 的仓库不包含本机备份和状态：

```bash
python3 integrate.py rollback
```

`.private/` 可能含订阅信息，只在本机保留，不要上传。若应用后有其它手动修改，回滚会拒绝覆盖，应在本机备份后手动审查和移除 `ONE EXIT` 标记块，保留后续修改。

## 维护和更新

### 1. 维护仓库名单

编辑 `one-exit-targets.list`，每行一个 Surge 匹配条件，不写策略、`[General]`、DNS 设置或完整节点。IP 规则必须带 `no-resolve`。现有 `DOMAIN-KEYWORD,claude/anthropic` 范围较宽，新增规则前需检查是否误匹配国内网站。

修改后，在此目录运行：

```bash
python3 build_module.py
python3 build_module.py --check
```

将源名单和生成的 `.sgmodule` 一起提交。脚本拒绝空名单、不支持的规则格式、额外策略列及缺少 `no-resolve` 的 IP 规则；它不代替 Surge 原生语法检查或实际分流测试。

更新上游时先审查差异，再手动移植需要的条目。这里维护独立快照，不自动同步上游删除或清空，也不直接导入 Shadowrocket 原模块。

### 2. 同步到当前内嵌配置

GitHub 文件更新不会自动修改已内嵌的主配置。先在本机备份当前配置，再只替换 `[Ruleset OneExitTargets]` 的内容，止于下一个 `[Ruleset OneExitKeepDirect]` 节头；保留节头、直连保护集、主逻辑规则以及 General/DNS。源名单中的注释可以保留。

通过 Surge 配置校验并重新载入后，检查 Claude、Google 等目标的策略链，以及百度、淘宝、国内视频和游戏仍按预期分流。再做一次 BrowserLeaks DNS 测试。此类手动更新会令旧 `integrate.py rollback` 的整文件哈希保护生效；之后回退应使用此次更新前的本机备份。

### 3. 可选：以后改用仓库远程名单

如需 GitHub 改动随 Surge 外部资源更新生效，可以在备份后，将已有逻辑规则中的 **第一个** `RULE-SET,OneExitTargets,no-resolve` 换成下面的 Raw URL，保留直连保护条件和策略：

```ini
AND,((RULE-SET,https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/one-exit-surge/one-exit-targets.list,no-resolve),(NOT,((RULE-SET,OneExitKeepDirect,no-resolve)))),♻️ 手动切换
```

此示例要求配置中已经存在 `OneExitKeepDirect` 和「♻️ 手动切换」。原来的内嵌目标集可保留作参考；此逻辑规则此后读取远程名单。不要直接添加一条无直连保护的顶层规则来替代它。

这属于另一种接入方式，本次上传仓库并未替本机切换。采用后需手动刷新 Surge 外部资源或等待其刷新周期，并重新检查分流。GitHub 提交不会立刻推送到设备；离线首次下载和服务可用性也会影响更新。需要固定版本时可将 URL 中的 `main` 换为审查过的提交 SHA。

## Raw 链接

- [源名单](https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/one-exit-surge/one-exit-targets.list)
- [可选数据 Module](https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/one-exit-surge/one-exit-targets.sgmodule)

## 验证与来源

初版在 Surge Mac 6.10 环境通过原生校验，并比较了集成前后 20 个域名/IP 的最终分流，原决策保持一致。每次修改后仍应自行复测；一次浏览器 DNS 结果只代表当次浏览器和节点。

- [One Exit 原始模块](https://github.com/wquguru/one-exit/blob/main/shadowrocket/one-exit.module)
- [Surge Module](https://manual.nssurge.com/profile/module.html)
- [Surge 逻辑规则](https://manual.nssurge.com/rules/logical.html)
- [Surge 规则集与 no-resolve](https://manual.nssurge.com/rules/ruleset.html)
