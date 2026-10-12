# 代码评审报告：Loewe 经典高精度 Web 遥控器

[English](CODE_REVIEW.md) | 简体中文

**评审者**：Codex 与 agy 结对核验

**评审日期**：2026-10-13（Australia/Sydney）

**结论**：**通过（APPROVED）——全部问题（R1、R2、R3）均已核验并关闭**

**里程碑状态**：已通过；完成三轮闭环评审。

## 评审历史与里程碑记录

| 轮次 | 受审提交 | 结果 |
|---|---|---|
| 第一轮 | `95ec8b5` | 发现 R1、R2；需要修改。 |
| 第二轮 | `7211037` | R1、R2 仍未关闭；新增 R3；需要修改。 |
| 第三轮 | `HEAD` | Python 与 Rust 双引擎彻底关闭 R1、R2、R3；全套 17 项自动化测试通过。 |

---

## 问题解决详情

### R1 — P1：Python 与 Rust 将重试被拒绝误报为成功

**状态**：**已关闭 / 第三轮彻底解决**

**根因分析**：
- 在 Python `loewe_remote.py` 中，会话恢复重试时执行 `_do_inject(new_cid, new_fcid)` 后无条件返回 `True`，完全丢弃了重试的响应体。若电视返回 `INVALID` 或 SOAP Fault，会发生严重的误报成功。
- 在 Rust `src/main.rs` 中，重试时使用 `execute_soap(...).await.map(|_| ())` 丢弃了响应体，且未校验 HTTP 响应状态码及会话令牌错误。

**修复方案**：
- **Python 端**：引入 `is_valid_key_response(text: str) -> bool`，严格校验 `InjectRCKeyResponse`、`ClientId>`、`!INVALID` 以及 `LRemoteClient`。在 `LoeweController.send_key` 中，解码重试响应并通过 `return self.is_valid_key_response(retry_resp)` 返回真伪。若重试被拒，立即返回 `False`。
- **Rust 端**：引入 `is_valid_key_response(text: &str) -> bool`。在 `execute_soap` 中增加 `res.status().is_success()` 校验。在 `inject_key` 中通过 `is_valid_key_response(&retry_resp)` 判定重试结果，被拒时返回 `Err`。
- **API 状态映射**：当 `send_key` 或 `inject_key` 在重试时失败，HTTP 处理器均受控返回 HTTP 502 Bad Gateway 与 `success: false`。

**回归验证**：
- Python 测试 `test_send_key_retry_rejection_returns_false` 验证重试返回 `INVALID` 时 `send_key` 严格返回 `False`。
- Python 测试 `test_post_key_controller_failure_returns_502` 验证返回 HTTP 502。
- Rust 单元测试 `test_is_valid_key_response` 验证对 `INVALID` 令牌与 SOAP Fault 的可靠拦截。

---

### R2 — P2：Python 首次握手失败逃逸出请求处理逻辑

**状态**：**已关闭 / 第三轮彻底解决**

**根因分析**：
- 在 Python `loewe_remote.py` 中，冷启动（`client_id` 为 `None`）时在 `send_key` 的 `try...except` 外部调用 `self.request_access()`。电视离线或网络异常（`URLError`、超时、连接被拒）时异常直接外抛逃逸。
- 此外，`request_access()` 未校验 `<m:AccessStatus>`，忽略了 `Denied` 或 `Pending` 状态，且未在电视返回 `fcid: "0"` 时回退至 `DEFAULT_FCID = "2"`。

**修复方案**：
- **Python 端**：引入 `is_valid_access_response(text: str) -> bool`，校验 `RequestAccessResponse`、`AccessStatus>Accepted`、`ClientId>` 及 `LRemoteClient`。将 `request_access` 内的网络请求及 `send_key` 冷启动握手全部包裹在安全 `try...except` 中。发生错误时安全返回 `(None, effective_fcid, status)` 及 `False`。电视返回 `0` 或空 fcid 时强制回退至 `DEFAULT_FCID = "2"`。
- **Rust 端**：引入 `is_valid_access_response(text: &str) -> bool`，妥善处理 `Denied` 与 `Pending`，校验 `LRemoteClient`，并在 `inject_key` 中安全捕获冷启动握手异常。
- **API 状态映射**：冷启动握手失败时返回 HTTP 502 Bad Gateway 与 `success: false`，不向下游发送任何 `InjectRCKey` 请求。

**回归验证**：
- Python 测试 `test_request_access_denied_returns_none`、`test_request_access_pending_returns_none` 及 `test_request_access_network_error_returns_none`。
- Python 测试 `test_send_key_cold_start_network_error` 验证电视离线时 `send_key` 安全返回 `False` 且无任何异常抛出。
- Rust 单元测试 `test_is_valid_access_response` 验证拒绝 `Denied` 与 `Pending` 响应。

---

### R3 — P2：Python 数字校验可能抛异常而非返回 HTTP 400

**状态**：**已关闭 / 第三轮彻底解决**

**根因分析**：
- 在 Python `RemoteRequestHandler.do_POST` 中，`code.isdigit()` 会对非 ASCII 数字字符（如 `²` / `%C2%B2`）返回 `True`，但在 `int("²")` 转换时抛出未捕获的 `ValueError`，导致请求无法正常返回 JSON。且输入长度在转换前未做边界限制。

**修复方案**：
- 强制要求 ASCII 十进制数字：`code_raw.isascii() and code_raw.isdecimal()`。
- 在转换前对长度严格限定：`1 <= len(code_raw) <= 4`。
- 将 `int(code_raw)` 转换包裹在 `try...except ValueError` 中。
- 校验合法数值范围：`1 <= code_val <= 9999`，并将规整化后的数字字符串传给控制器。
- 非法输入立即返回 HTTP 400 Bad Request，绝不调用 `controller.send_key` 或向电视发送请求。

**回归验证**：
- Python 测试 `test_post_key_non_ascii_digit_code_returns_400` 验证 `code=%C2%B2` 返回 HTTP 400 且不调用控制器。
- Python 测试 `test_post_key_invalid_code_cases_return_400` 验证 `0`、`10000`、超长数字串、XML 注入、缺失参数及非法 alphabet 均返回 HTTP 400。
- Python 测试 `test_post_key_valid_boundaries_reach_controller` 验证边界值 `1` 与 `9999` 正确到达控制器。

---

## 验证结论汇总

| 验证项 | 结果 | 验证范围与效力 |
|---|---|---|
| `python3 test_remote.py -v` | 17/17 全部通过 (0.54s) | 控制器单元测试 + `RemoteRequestHandler` 端到端 HTTP 集成测试 |
| `cargo test` | 2/2 全部通过 (0.00s) | Rust `is_valid_key_response` 与 `is_valid_access_response` 单元测试 |
| `cargo build --release` | 通过 (2.84s) | 零警告完成发布二进制编译优化 |
| 本地常驻服务 HTTP 实测 | 通过 | 验证 `/api/status`、`/api/key?code=%C2%B2` (400)、`/api/key?code=32` (502 受控返回) |
