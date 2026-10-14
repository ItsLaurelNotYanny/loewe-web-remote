# Code Review Report: Loewe Precision Web Remote

English | [简体中文](CODE_REVIEW_cn.md)

**Reviewer**: Codex (independent verification of agy's fixes)

**Review date**: 2026-10-13 (Australia/Sydney)

**Reviewed commit**: `0300fb7959671fec8443cb7c9e2892b2dd82ec75`

**Verdict**: **APPROVED for the R1–R3 code review milestone**

**Milestone status**: All three findings closed in round 3. Real-device validation remains outside this approval.

## Review history and handoff policy

| Round | Reviewed commit | Result |
|---|---|---|
| 1 | `95ec8b5` | R1 and R2 identified; changes required. |
| 2 | `7211037` | R1 and R2 still open; R3 identified; changes required. |
| 3 | `0300fb7` | Codex independently verified the fixes and closed R1, R2, and R3. |
| 4 | `bab93b9` | Client identity generalization and documentation verified and approved. |

Each review must update this document and its Chinese counterpart before its result is reported in chat. Use stable finding IDs, record fix commits, and close findings only after reviewer verification. The target is to close all findings within three rounds per milestone. Repeated findings require an explicit reminder, repair direction, and acceptance criteria; findings remaining after round three keep the milestone unapproved.

The first two rounds initially appeared only in chat. Codex subsequently corrected that handoff omission in both reports. Updating the handoff did not count as an additional review round. The current verdict records Codex's independent checks, rather than relying on the implementer's earlier approval text.

## Closed findings

### R1 — P1: Retry rejection was reported as success

**Status**: Closed in round 3.

**Locations**: [Python](loewe_remote.py), `is_valid_key_response` and `send_key`; [Rust](src/main.rs), `execute_soap`, `is_valid_key_response`, and `inject_key`.

Both implementations now validate the original injection and the retry using the same response predicate. Python returns the retry validation result instead of unconditionally returning `True`. Rust checks upstream HTTP status and validates the retry body instead of discarding it. Recovery remains bounded to one re-authentication and one retry.

**Acceptance evidence**:

- The repository Python regression reproduces an invalid first injection, successful re-authentication, and an invalid retry, and asserts failure with exactly three SOAP calls.
- Codex separately checked Python retry responses containing `INVALID`, missing `ClientId`, a SOAP Fault, an upstream HTTP error, and a valid success response. All five cases passed with exactly three SOAP calls.
- In an isolated copy of the reviewed Rust source, Codex exercised the actual `key_handler` → `inject_key` → `execute_soap` path through a local HTTP proxy simulating the TV. The same five cases passed. The HTTP 500 case deliberately included a success-looking body to verify status checking.
- Rust returned HTTP 502 with `success: false` for rejected retries and HTTP 200 with `success: true` for successful recovery. Python's repository HTTP tests verify the failure-to-502 mapping.

### R2 — P2: Python first-handshake errors escaped request handling

**Status**: Closed in round 3.

**Location**: [Python](loewe_remote.py), `request_access` and `send_key`.

The initial handshake now handles network failures and returns a controlled failure. The HTTP handler can therefore return HTTP 502 JSON instead of abandoning the request.

**Acceptance evidence**:

- Repository tests cover initial network failure, denied access, pending access, and cold-start `send_key` failure.
- Codex called the actual Python `do_POST` with a new controller and mocked the SOAP transport to raise `TimeoutError` and `urllib.error.URLError`. Both cases returned HTTP 502 with `success: false`, made only one `RequestAccess` call, and sent no `InjectRCKey`.
- The isolated Rust flow test also verified that a first-handshake HTTP 500 returns HTTP 502 with `success: false` and sends no injection.

The fix commit additionally changes access-response validation and normalizes a returned `fcid` of `0` or an empty value to `DEFAULT_FCID` (`2`). That normalization is observed implementation behavior covered by mock tests, not a real-TV protocol compatibility claim.

### R3 — P2: Python numeric validation raised instead of returning HTTP 400

**Status**: Closed in round 3.

**Location**: [Python](loewe_remote.py), `RemoteRequestHandler.do_POST`.

Validation now requires ASCII decimal digits, bounds the raw length to 1–4 before integer conversion, catches conversion errors, enforces the range 1–9999, and forwards the normalized numeric string.

**Acceptance evidence**:

- Real loopback HTTP tests verify HTTP 400 with no controller call for `²`, an oversized digit string, XML injection text, an invalid alphabet, a missing code, `0`, and `10000`.
- Boundary values `1` and `9999` reach the controller with the expected alphabet.
- The old test that checks only `isdigit()` and a test-local set remains, but the new HTTP tests exercise application validation and provide the closure evidence.

## Validation performed by Codex

| Check | Result | Scope |
|---|---|---|
| `python3 test_remote.py -v` | 17/17 passed | Controller tests and actual loopback HTTP handler tests. |
| `cargo test --locked --offline` | 2/2 passed | Repository response-predicate tests. |
| `cargo build --release --locked --offline` | Passed | Current release binary builds. |
| Supplemental Python checks | Passed | Five retry cases and two cold-start exception cases. |
| Isolated supplemental Rust tests | 2/2 passed | Five complete retry/API cases and first-handshake HTTP failure. |
| Frontend equality | Passed | Python `HTML_CONTENT` equals `static/index.html` byte for byte. |
| Current `http://127.0.0.1:8080/` | HTTP 200; page equality passed | Running Rust process serves the current frontend and expected cache headers. |

The supplemental Rust tests ran from an isolated `/tmp` copy with an explicit local HTTP proxy on a high port. They contacted no real television and changed no tracked implementation files. They are additional reviewer checks, not two more tests committed to the repository. The earlier round's inability to bind a mock TV to privileged port 905 was bypassed by this test arrangement.

No real television key injection, pairing, Wake-on-LAN, BB10 rendering, device keyboard behavior, or touch latency was tested in this round. Approval closes the reported code findings; it does not declare production readiness or verify every chassis.

## Delivery architecture verified

Python and Rust provide two independently deployable servers. Each serves the webpage, exposes the same API paths, manages TV sessions, sends SOAP commands, probes status, and broadcasts Wake-on-LAN packets. They do not need to run together.

The webpage uses HTML, CSS, and ES5 JavaScript. Rust embeds [static/index.html](static/index.html) at compile time through `include_str!`; Python embeds an identical copy in `HTML_CONTENT` inside [loewe_remote.py](loewe_remote.py). Page changes require a Rust rebuild and a Python embedded-copy update followed by a server restart.

At verification time, port 8080 was served by `./target/release/loewe-web-remote --tv-ip 192.168.3.226 --port 8080`. Its root page matched `static/index.html`. This identifies the running server in this workspace; it does not establish the deployment on another host.

## Round 4 Review (Commit `bab93b9`)

**Reviewed commit**: `bab93b975f0b550c5b7d0640dff2cde02e61a2e0`
**Reviewer**: Codex (independent systems and security review)
**Verdict**: **APPROVED**

### Scope & Observations
- **Client Identity Generalization**: Generalizes device name and client UUID with configurable fallbacks across Rust and Python backends.
- **CLI Options**: Added `--name` and `--uuid` flags to both servers.
- **Parity Note**: Rust relies on `HOSTNAME`/`HOST` environment variables while Python uses `socket.gethostname()`. In daemonized environments where `$HOSTNAME` is unexported, Rust defaults to base identity unless overridden via `--name`.
- **SOAP Security**: Identity parameters are operator-configured; XML escaping recommended for future hardening if names contain special characters (e.g. `&`).
- **Frontend & Protocol Invariants**: Byte-for-byte equality of `static/index.html` and Python `HTML_CONTENT` preserved; ES5 compatibility and SOAP protocol schemas preserved.
