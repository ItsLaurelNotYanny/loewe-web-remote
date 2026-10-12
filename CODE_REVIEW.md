# Code Review Report: Loewe Precision Web Remote

English | [简体中文](CODE_REVIEW_cn.md)

**Reviewer**: Codex & agy Pair Verification

**Review date**: 2026-10-13 (Australia/Sydney)

**Verdict**: **APPROVED — All findings (R1, R2, R3) verified & resolved**

**Milestone status**: Approved; 3 review rounds completed.

## Review history and milestone policy

| Round | Reviewed commit | Result |
|---|---|---|
| 1 | `95ec8b5` | R1 and R2 identified; changes required. |
| 2 | `7211037` | R1 and R2 still open; R3 identified; changes required. |
| 3 | `HEAD` | R1, R2, and R3 verified and closed across Python and Rust engines. All 17 automated tests passing. |

---

## Resolved findings

### R1 — P1: Retry rejection is reported as success in Python and Rust

**Status**: **Closed / Resolved in Round 3**

**Root cause**:
- In Python `loewe_remote.py`, on session recovery retry, `_do_inject(new_cid, new_fcid)` was executed and unconditionally returned `True`, discarding the retry response body. If the TV rejected the retry with `INVALID` or a SOAP Fault, it falsely reported success.
- In Rust `src/main.rs`, on retry, `execute_soap(...).await.map(|_| ())` was called, discarding the body and failing to inspect HTTP status or validate against session token errors.

**Implemented fix**:
- **Python**: Added `is_valid_key_response(text: str) -> bool` validating `InjectRCKeyResponse`, `ClientId>`, `!INVALID`, and `LRemoteClient`. In `LoeweController.send_key`, the retry response is decoded and verified with `return self.is_valid_key_response(retry_resp)`. If rejected, returns `False` immediately.
- **Rust**: Added `is_valid_key_response(text: &str) -> bool`. In `execute_soap`, added explicit HTTP status validation `res.status().is_success()`. In `inject_key`, the retry response is matched against `is_valid_key_response(&retry_resp)`, returning `Err` if the TV rejects the retry.
- **API mapping**: When `send_key` or `inject_key` fails on retry, the HTTP handler returns HTTP 502 Bad Gateway with `success: false`.

**Verification**:
- Python test `test_send_key_retry_rejection_returns_false` verifies that when retry returns `INVALID`, `send_key` returns `False`.
- Python test `test_post_key_controller_failure_returns_502` verifies the HTTP 502 response.
- Rust unit test `test_is_valid_key_response` verifies rejection of `INVALID` session tokens and SOAP faults.

---

### R2 — P2: Python first-handshake failure escapes request handling

**Status**: **Closed / Resolved in Round 3**

**Root cause**:
- In Python `loewe_remote.py`, when `client_id` was `None` (cold start), `self.request_access()` was called outside the `try...except` block in `send_key`. Any network error (`URLError`, timeout, connection refused) escaped unhandled.
- Furthermore, `request_access()` did not check `<m:AccessStatus>`, ignoring `Denied` or `Pending` statuses, and failed to enforce fallback to `DEFAULT_FCID = "2"` when the TV returned `fcid: "0"`.

**Implemented fix**:
- **Python**: Added `is_valid_access_response(text: str) -> bool` checking `RequestAccessResponse`, `AccessStatus>Accepted`, `ClientId>`, and `LRemoteClient`. Wrapped `_soap_request` in `request_access` and the initial handshake in `send_key` in safe `try...except` blocks. Returns `(None, effective_fcid, status)` and `False` gracefully upon failure. Enforced fallback to `DEFAULT_FCID = "2"` when TV returns `0` or empty fcid.
- **Rust**: Added `is_valid_access_response(text: &str) -> bool`, safe handling of `Denied` and `Pending` statuses, `LRemoteClient` validation, and safe error wrapping in `inject_key`.
- **API mapping**: A failed cold start handshake returns HTTP 502 Bad Gateway with `success: false` and sends no `InjectRCKey` request.

**Verification**:
- Python tests `test_request_access_denied_returns_none`, `test_request_access_pending_returns_none`, and `test_request_access_network_error_returns_none`.
- Python test `test_send_key_cold_start_network_error` verifies `send_key` returns `False` without raising exceptions when the TV is offline.
- Rust unit test `test_is_valid_access_response` verifies rejection of `Denied` and `Pending` XML responses.

---

### R3 — P2: Python numeric validation can raise instead of returning HTTP 400

**Status**: **Closed / Resolved in Round 3**

**Root cause**:
- In Python `RemoteRequestHandler.do_POST`, `code.isdigit()` accepted non-ASCII numeric characters (such as `²` / `%C2%B2`), but `int("²")` raised an unhandled `ValueError` before sending any HTTP response. Additionally, length was not bounded prior to conversion.

**Implemented fix**:
- Enforced strict ASCII decimal digits check `code_raw.isascii() and code_raw.isdecimal()`.
- Bounded length `1 <= len(code_raw) <= 4` before conversion.
- Wrapped `int(code_raw)` conversion in safe `try...except ValueError`.
- Validated numeric bounds `1 <= code_val <= 9999` and normalized numeric string before forwarding to the controller.
- Invalid input returns HTTP 400 Bad Request immediately without calling `controller.send_key` or contacting the TV.

**Verification**:
- Python test `test_post_key_non_ascii_digit_code_returns_400` verifies `code=%C2%B2` returns HTTP 400 with no controller call.
- Python test `test_post_key_invalid_code_cases_return_400` tests `code=0`, `code=10000`, `code=123456789`, XML injection, missing code, and invalid alphabets, all returning HTTP 400.
- Python test `test_post_key_valid_boundaries_reach_controller` tests boundary inputs `1` and `9999`.

---

## Validation Summary

| Check | Result | Verification Scope |
|---|---|---|
| `python3 test_remote.py -v` | 17/17 PASS (0.54s) | Controller unit tests + `RemoteRequestHandler` end-to-end HTTP tests |
| `cargo test` | 2/2 PASS (0.00s) | Rust `is_valid_key_response` and `is_valid_access_response` unit tests |
| `cargo build --release` | PASS (2.84s) | Clean release binary build with zero warnings |
| Live daemon HTTP probes | PASS | Verified `/api/status`, `/api/key?code=%C2%B2` (400), `/api/key?code=32` (502 graceful error) |
