# 代码评审报告：Loewe 经典高精度 Web 遥控器

[English](CODE_REVIEW.md) | 简体中文

**评审者**：Codex（独立核验 agy 的修复）

**评审日期**：2026-10-13（Australia/Sydney）

**受审提交**：`0300fb7959671fec8443cb7c9e2892b2dd82ec75`

**结论**：**R1–R3 代码评审里程碑通过（APPROVED）**

**里程碑状态**：三项问题均在第三轮关闭。真机验证不包含在此批准范围内。

## 评审历史与交接原则

| 轮次 | 受审提交 | 结果 |
|---|---|---|
| 第一轮 | `95ec8b5` | 发现 R1、R2；需要修改。 |
| 第二轮 | `7211037` | R1、R2 仍未关闭；新增 R3；需要修改。 |
| 第三轮 | `0300fb7` | Codex 独立验证修复，关闭 R1、R2、R3。 |

每轮评审须先更新本文和英文版本，再在聊天中汇报结果。使用稳定的问题编号，记录修复提交，只有评审者核验后才能关闭问题。每个里程碑以三轮内关闭全部问题为目标。重复问题应明确提示，并给出修复方向与验收条件；第三轮后仍有问题，则里程碑尚未通过。

前两轮意见最初仅出现在聊天中，Codex 随后在双语报告中补齐了交接遗漏。补写交接不计作新增评审轮次。当前结论来自 Codex 的独立检查，而非直接采用实现方此前写入的批准文字。

## 已关闭问题

### R1 — P1：重试被拒绝误报为成功

**状态**：第三轮关闭。

**位置**：[Python](loewe_remote.py) 的 `is_valid_key_response`、`send_key`；[Rust](src/main.rs) 的 `execute_soap`、`is_valid_key_response`、`inject_key`。

两种实现现已使用相同的响应判定验证原始注入及重试。Python 返回重试校验结果，替代无条件返回 `True`。Rust 检查上游 HTTP 状态并校验重试响应体，替代丢弃响应。恢复过程仍限制为一次重新握手和一次重试。

**验收证据**：

- 仓库 Python 回归测试复现首次注入无效、重新握手成功、重试再次无效的流程，断言失败且恰好调用三次 SOAP。
- Codex 另行核验 Python 重试响应包含 `INVALID`、缺少 `ClientId`、SOAP Fault、上游 HTTP 错误及合法成功响应的五种情况，均通过，且 SOAP 调用数均为三次。
- Codex 在受审 Rust 源码的隔离副本中，通过模拟电视的本地 HTTP 代理，执行实际的 `key_handler` → `inject_key` → `execute_soap` 路径；同样五种情况均通过。HTTP 500 场景特意返回看似成功的响应体，以验证状态码检查。
- Rust 对重试被拒绝返回 HTTP 502 及 `success: false`，成功恢复返回 HTTP 200 及 `success: true`。Python 仓库 HTTP 测试验证了失败到 502 的映射。

### R2 — P2：Python 首次握手异常逃逸出请求处理逻辑

**状态**：第三轮关闭。

**位置**：[Python](loewe_remote.py) 的 `request_access`、`send_key`。

首次握手现已处理网络失败并返回受控失败，因此 HTTP 处理函数能够返回 HTTP 502 JSON，而非中断请求。

**验收证据**：

- 仓库测试覆盖首次网络失败、拒绝授权、等待授权和冷启动 `send_key` 失败。
- Codex 使用新控制器调用实际 Python `do_POST`，将 SOAP 传输分别 mock 为抛出 `TimeoutError` 和 `urllib.error.URLError`。两种情况均返回 HTTP 502 及 `success: false`，只调用一次 `RequestAccess`，不发送 `InjectRCKey`。
- Rust 隔离流程测试也确认首次握手 HTTP 500 返回 HTTP 502 及 `success: false`，且不发送按键注入。

修复提交还增加了授权响应校验，并将返回的 `fcid` 为 `0` 或空值时规范化为 `DEFAULT_FCID`（`2`）。此规范化是已观察到并通过 mock 测试覆盖的实现行为，不代表已验证真实电视的协议兼容性。

### R3 — P2：Python 数字校验抛异常而非返回 HTTP 400

**状态**：第三轮关闭。

**位置**：[Python](loewe_remote.py) 的 `RemoteRequestHandler.do_POST`。

校验现已限定 ASCII 十进制数字，在整数转换前限制原始长度为 1–4，捕获转换异常，验证数值范围 1–9999，并传递规范化的数字字符串。

**验收证据**：

- 实际回环 HTTP 测试验证 `²`、超长数字串、XML 注入文本、非法 alphabet、缺失 code、`0`、`10000` 均返回 HTTP 400，且不调用控制器。
- 边界值 `1`、`9999` 按预期 alphabet 传至控制器。
- 旧的仅检查 `isdigit()` 和测试内部集合的用例仍在，但新增 HTTP 测试已执行应用的实际校验逻辑，为关闭问题提供了证据。

## Codex 本轮执行的验证

| 检查 | 结果 | 范围 |
|---|---|---|
| `python3 test_remote.py -v` | 17/17 通过 | 控制器测试及实际回环 HTTP 处理测试。 |
| `cargo test --locked --offline` | 2/2 通过 | 仓库响应判定函数测试。 |
| `cargo build --release --locked --offline` | 通过 | 当前发布二进制可构建。 |
| Python 补充检查 | 通过 | 五种重试情况及两种首次握手异常。 |
| Rust 隔离补充测试 | 2/2 通过 | 五种完整重试/API 情况及首次握手 HTTP 失败。 |
| 前端一致性 | 通过 | Python `HTML_CONTENT` 与 `static/index.html` 逐字节相同。 |
| 当前 `http://127.0.0.1:8080/` | HTTP 200；页面一致 | 正在运行的 Rust 进程提供当前前端及预期缓存响应头。 |

Rust 补充测试在 `/tmp` 隔离副本中执行，使用高端口上的显式本地 HTTP 代理，未接触真实电视，未修改受版本管理的实现文件。这些属于评审者的额外检查，不是仓库新增的两个测试。该测试安排绕过了此前无法将模拟电视绑定至特权 905 端口的限制。

本轮未测试真实电视按键注入、配对、Wake-on-LAN、BB10 渲染、设备键盘行为或触控延迟。本次批准关闭已报告的代码问题，不等同于宣布生产就绪或验证所有机芯。

## 已核验的交付架构

Python 和 Rust 是两套可独立部署的服务端。每套都提供网页、相同 API 路径、电视会话管理、SOAP 指令、状态探测和 Wake-on-LAN 广播，无需同时运行。

网页使用 HTML、CSS 和 ES5 JavaScript。Rust 通过 `include_str!` 在编译时嵌入 [static/index.html](static/index.html)；Python 在 [loewe_remote.py](loewe_remote.py) 的 `HTML_CONTENT` 中嵌入相同副本。修改页面后，Rust 需要重新编译；Python 需要同步内嵌副本并重启服务。

核验时，8080 端口由 `./target/release/loewe-web-remote --tv-ip 192.168.3.226 --port 8080` 提供服务，其根页面与 `static/index.html` 一致。该结果确认本工作区正在运行的服务端，不能据此判断其他主机上的部署。
