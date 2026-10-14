# Code Review Report: Loewe Precision Web Remote

English | [简体中文](CODE_REVIEW_cn.md)

**Reviewer**: Codex (independent verification of agy's fixes)

**Review date**: 2026-10-15 (Australia/Sydney)

**Reviewed commit**: `62ef2494a94d70205e7eac16bf41b98bcf4d746e`

**Verdict**: **APPROVED — R1–R5 closed**

**Milestone status**: R1–R5 are independently closed. The client configuration/documentation milestone is approved within three rounds; real-device validation remains outside this review.

## Review history and handoff policy

| Round | Reviewed commit | Result |
|---|---|---|
| 1 | `95ec8b5` | R1 and R2 identified; changes required. |
| 2 | `7211037` | R1 and R2 still open; R3 identified; changes required. |
| 3 | `0300fb7` | Codex independently verified the fixes and closed R1, R2, and R3. |
| 4 | `9d59f9e` (implementation `bab93b9`) | Independent recheck: user-reported changes present; R4 open; changes required. |
| 5 | `d25dbf8` (implementation `bca09dd`) | R4 independently verified and closed; R5 documentation finding open. |
| 6 | `62ef249` (fix `b2526ab`) | R5 independently verified and closed; R1–R5 milestone APPROVED. |

Each review must update this document and its Chinese counterpart before its result is reported in chat. Use stable finding IDs, record fix commits, and close findings only after reviewer verification. The target is to close all findings within three rounds per milestone. Repeated findings require an explicit reminder, repair direction, and acceptance criteria; findings remaining after round three keep the milestone unapproved.

The first two rounds initially appeared only in chat. Codex subsequently corrected that handoff omission in both reports. Updating the handoff did not count as an additional review round. The current verdict records Codex's independent checks, rather than relying on the implementer's earlier approval text.

### Review watch and repeated-failure policy

- After every review, update both `CODE_REVIEW.md` and `CODE_REVIEW_cn.md` with the exact reviewed commit, gate evidence, stable finding IDs, repair directions, and acceptance criteria. Commit the reports before declaring the handoff complete.
- While the review watch is active, check the current local branch for new commits every 15 minutes after the review-report commit. If remote tracking is configured, fetch it without merging, rebasing, resetting, or changing the author's working tree. Remote submissions must be reviewed in an isolated clean checkout.
- For a new code submission, independently run the full project gate on its exact clean commit before inspecting its diff. A gate failure or missing gate stops that review; record the bounded diagnostic without repairing the author's code.
- Distinguish implementation submissions from reviewer report/policy commits. A report-only commit is not a new repair attempt and must not trigger a review loop of the reviewer's own output.
- Track failed repair rounds by finding ID and submitted commit. If the same finding remains unresolved after two consecutive repair submissions, explicitly flag it in both reports and the user update, listing both commits, the reproduced failure, and the unmet acceptance criteria. Do not count the initial discovery, an unchanged polling result, a gate-only blockage, or a report-only commit as a failed repair round.
- Continue the watch after approval so later submissions are detected, until the user stops it. Persist the last observed/reviewed commit and next check time for recovery; if execution is interrupted, resume from that checkpoint and do not claim checks occurred during the interruption.
- This rule does not authorize publishing reviews or sending messages through external services. The shared repository reports and this chat are the handoff channels unless the user authorizes another channel.

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

### R4 — P2: Configurable client identity is inserted into SOAP without XML escaping

**Status**: Closed in round 5.

**Locations**: [Python](loewe_remote.py), `escape_xml` and `request_access`; [Rust](src/main.rs), `escape_xml` and `request_access`; [Python tests](test_remote.py), `test_request_access_xml_escaping`; [Rust tests](src/main.rs), `test_escape_xml`.

Both backends now escape XML entity characters (`&`, `<`, `>`, `"`, `'`) in `device_name` and `client_uuid` before serializing them into the `RequestAccess` SOAP envelope.

**Acceptance evidence**:

- `test_remote.py` test `test_request_access_xml_escaping` exercises `request_access` with `Living & Dining <Room> "Main"` and `client&uuid<1>`, captures the actual SOAP payload, parses it with `xml.etree.ElementTree`, and asserts that decoded values match the input without extra XML markup.
- `src/main.rs` test `test_escape_xml` verifies character escaping and standard name passthrough.
- Gate check passed: `OK: project-gate (full, checks=8)`.

### R5 — P2: New security documentation misstates the scope of TV port 905

**Status**: Closed in round 6; fixed by `b2526ab`; unsuccessful repair submissions: 0.

**Locations**: [README.md](README.md), section 6; [README_cn.md](README_cn.md), section 6.

Section 6 in both documentation versions now accurately bounds this application's interaction with port 905 (`loewe_tablet_0001`) to `RequestAccess` and `InjectRCKey`, removes unverified claims regarding firmware internals or exhaustive data exposure, and scopes the automatic acceptance observation to the tested Loewe bild 5.65 (SL520, software 6.7.9.0) with Mobile Control enabled.

**Acceptance evidence**:

- Both language versions state application actions factually without claiming exhaustive API ownership.
- Real-device observations explicitly identify the tested device and note potential variation across firmware or chassis.
- Gate check passed: `OK: project-gate (full, checks=8)`.

## Historical Round 3 Validation (2026-10-13)

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

## Historical Round 3 Delivery Verification (2026-10-13)

Python and Rust provide two independently deployable servers. Each serves the webpage, exposes the same API paths, manages TV sessions, sends SOAP commands, probes status, and broadcasts Wake-on-LAN packets. They do not need to run together.

The webpage uses HTML, CSS, and ES5 JavaScript. Rust embeds [static/index.html](static/index.html) at compile time through `include_str!`; Python embeds an identical copy in `HTML_CONTENT` inside [loewe_remote.py](loewe_remote.py). Page changes require a Rust rebuild and a Python embedded-copy update followed by a server restart.

At verification time, port 8080 was served by `./target/release/loewe-web-remote --tv-ip 192.168.3.226 --port 8080`. Its root page matched `static/index.html`. This identifies the running server in this workspace; it does not establish the deployment on another host.

## Round 4 Review — Client Configuration Milestone (Round 1)

**Review date**: 2026-10-15 (Australia/Sydney)

**Reviewed commit**: `9d59f9ebb503e6cf675d016ce8339ac352fb9caf`

**Implementation commit**: `bab93b975f0b550c5b7d0640dff2cde02e61a2e0`

**Verdict**: **CHANGES REQUIRED — R4 open**

The user confirmed that this submission addresses two problems: a client identity fixed to Synology, and deployment instructions that confused the server host with the television's network parameters. Both changes are present. This independent review supersedes the earlier round-4 approval text carried in `9d59f9e`; ordinary configured names containing XML characters already break pairing, so escaping is required for this milestone rather than deferred hardening. R1–R3 remain closed.

### Gate and snapshot evidence

- Ran `./check.sh` on the clean checkout of `9d59f9ebb503e6cf675d016ce8339ac352fb9caf` before inspecting the code diff.
- Result: `OK: project-gate (full, checks=8)`.
- Verified the commit and clean source state were unchanged after the checks.
- Reviewed the implementation and deployment-documentation changes from `0a19821` to `9d59f9e`.
- No implementation changes were made by the reviewer. This handoff updates only the two review reports; the gate result applies to the named committed snapshot.

### User-reported fixes verified

| User-reported problem | Observed change | Assessment |
|---|---|---|
| Identity fixed to Synology | Both backends use generic defaults and expose `--name` and `--uuid`. The selected values reach the controller/state. | Fixed for ordinary XML-safe values; R4 affects the new configuration path. |
| Server and TV network parameters unclear | README identifies `--tv-ip` and `--mac` as television parameters and `http://<SERVER_IP>:8080` as the browser's server address. | Addressed in the deployment instructions. |

Rust derives its default suffix from `HOSTNAME`/`HOST`; Python uses `socket.gethostname()`. These defaults can differ when environment variables are absent. Explicit `--name` and `--uuid` avoid relying on backend-specific hostname inference. Existing tests still do not directly cover CLI identity resolution; add this coverage with the R4 regression tests.

### R4 — P2: Configurable client identity is inserted into SOAP without XML escaping

**Status at round 4**: Open. Closed in round 5; see the closure evidence below.

**Locations at the reviewed commit**:

- [Python](loewe_remote.py): `request_access`, lines 820–824; CLI configuration, lines 983–994.
- [Rust](src/main.rs): `request_access`, lines 253–260; CLI identity resolution, lines 467–488.

**Trigger and impact**: Start either backend with `--name "Living & Dining"` or a `--uuid` containing `&`. The request builder places these strings directly into `DeviceName`, `DeviceUUID`, and `RequesterName`. An ordinary display name can therefore produce malformed XML and prevent the TV from accepting the pairing request. A name containing `<Room>` also produces malformed XML, and arbitrary markup is inserted as markup rather than text.

**Evidence**: Codex mocked Python's SOAP transport, captured the actual `RequestAccess` body, and parsed it using `xml.etree.ElementTree`. Names `Living & Dining` and `Living <Room>`, and UUID `client&one`, failed XML parsing; the ordinary `Living Room` / `client-1` control parsed successfully. Rust's matching unescaped `format!` interpolation is confirmed by source inspection; no real TV pairing was attempted.

**Required fix**: Serialize all configurable identity values as XML text in both backends. Use an XML serializer or consistent text escaping for `&`, `<`, and `>`; apply it to both occurrences of the device name and to the UUID. Preserve the user's original decoded text. This is a functional correctness issue for operator-supplied values, not merely a future security enhancement.

**Acceptance criteria**:

- Exercise the actual request-building paths in both languages with special characters in `--name` and `--uuid`.
- The captured SOAP payload parses successfully, and decoded `DeviceName`, `RequesterName`, and `DeviceUUID` match the original input.
- Markup-like input remains text and creates no extra XML elements.
- Ordinary values and generic defaults continue to work; cover explicit CLI overrides and hostname/default fallback.
- Re-run the full gate on a clean fix commit before handing off. Report the fix commit and regression results under R4, then request independent closure.

### Limits and next handoff

The gate checks and reproductions used local mocks or loopback tests, without controlling a real television. Previous R1–R3 approval is retained as historical evidence. R4 has been fixed and verified in Round 5.

## Round 5 Review — Client Configuration Milestone (Round 2)

**Review date**: 2026-10-15 (Australia/Sydney)

**Reviewed commit**: `d25dbf83eef6bb803cd6c5d9cde540c45ecc6f02`

**Implementation commit**: `bca09dd4c288ce636af19d91dffb50032289ef3f`

**Verdict**: **CHANGES REQUIRED — R4 closed; R5 documentation finding open**

This independent review closes R4 after one repair submission. It supersedes the blanket approval written in the report-only commit `d25dbf8`. R1–R3 remain closed. The new documentation finding below is distinct from R4 and is not counted as a failed R4 repair.

### Gate and exact-target evidence

- The 09:21 Sydney polling check discovered `bca09dd`.
- The author initially had uncommitted report changes, so Codex created a detached clean worktree at that exact implementation commit without resetting, stashing, or changing the author's files.
- Ran `./check.sh` before inspecting the implementation diff: `OK: project-gate (full, checks=8)`.
- The author subsequently committed the reports as `d25dbf8`. Codex ran the full gate again on that clean exact commit, with the same passing result.
- Confirmed that implementation, tests, and README content are unchanged between `bca09dd` and `d25dbf8`.
- These gate results apply to the named committed snapshots; the reviewer changes only the bilingual reports.

### R4 closure evidence

**Status**: Closed in round 5; fixed by `bca09dd`; unsuccessful repair submissions: 0.

Both backends escape the device name and UUID before constructing `RequestAccess`, including both `DeviceName` and `RequesterName`. The repository adds Python's `test_request_access_xml_escaping` and Rust's `test_escape_xml`.

Codex additionally verified five identity pairs: ampersands, angle brackets and quotes, markup-like text, literal entity-looking text, and generic defaults. For both languages, the actual generated request payloads parse successfully and the decoded identity values exactly match the original input; each identity field appears once and contains no child elements. No injected elements are created.

For Rust, an isolated copy of the reviewed implementation exercised the actual `request_access` and `execute_soap` functions through a local high-port HTTP proxy; Python parsed the captured SOAP payloads using `xml.etree.ElementTree`. The probe also exercised explicit `--name` and `--uuid` parsing. For Python, the actual request builder was checked with a mocked SOAP transport, and the main entry point was checked for explicit overrides, hostname-derived defaults, and empty-host fallback. Rust's unchanged hostname fallback was inspected, not separately exercised through its main entry point.

The supplementary probe files are temporary reviewer artifacts, not new tests committed to the repository. No real television was contacted. The full gate checks page-copy equality and JavaScript syntax; this is not an ES5 parser or real BB10 compatibility test.

### R5 — P2: New security documentation misstates the scope of TV port 905

**Status in Round 5**: Open; closed in round 6 by commit `b2526ab`.

**Location**: [README.md](README.md), section 6, line 165, and the matching section of [README_cn.md](README_cn.md).

**Problem and evidence**: The new text says that port 905 exclusively handles `InjectRCKey` and exposes no account credentials, browsing history, or private media. The first claim conflicts with this project's own behavior: both backends send `RequestAccess` to the same port and `loewe_tablet_0001` endpoint. The application using a subset of TV actions also does not establish that the TV endpoint exposes no other data. This review has not audited the TV's complete endpoint surface or independently reproduced the new real-device authentication claims.

**Impact**: Deployment guidance presents a broader capability and privacy assurance than the verified application behavior supports. Operators cannot use this application review as evidence of the full television API's security scope.

**Required fix**: Narrow section 6 in both READMEs to the application behavior and any precisely identified device observations. State that this application uses `RequestAccess` and `InjectRCKey` on port 905, rather than describing that as the complete API surface. Remove the exhaustive private-data assurance unless it is supported by appropriately scoped evidence. Describe the automatic acceptance observation as specific to the tested device/settings/firmware; do not present it as a universal authorization guarantee.

**Acceptance criteria**:

- Both README language versions describe the app's actions accurately and contain no unsupported exclusivity or exhaustive privacy claim.
- Distinguish any observed acceptance behavior from inference about the TV's complete trust/security model; cite or attach the specific evidence when retaining real-device claims.
- No broad hardware audit is required to close this finding: a factual, bounded description is sufficient.
- Run the full gate on the clean documentation-fix commit before review handoff.

### Finding tracking and next check

R4 is resolved after its first repair submission; it does not meet the repeated-failure threshold. R5 is newly discovered and has no failed repair submissions. The two-failure reminder is therefore not due. Commit this bilingual handoff, then schedule the next poll 15 minutes after the report commit and continue watching.

## Round 6 Review — Client Configuration & Device Documentation Milestone (Round 3 — Final Approval)

**Review date**: 2026-10-15 (Australia/Sydney)

**Reviewed commit**: `62ef2494a94d70205e7eac16bf41b98bcf4d746e`

**Verdict**: **APPROVED — R1–R5 closed**

Commit `b2526ab` completely and accurately resolves Finding R5 across both language documentations:
1. **Accurate Application Scope on Port 905**: Section 6 of both [`README.md`](README.md) and [`README_cn.md`](README_cn.md) explicitly states that this application interacts with port 905 (`loewe_tablet_0001` endpoint) solely to execute `RequestAccess` and `InjectRCKey`. Unverified claims regarding firmware internals or exhaustive data exposure have been removed.
2. **Properly Bounded Real-Device Observations**: The observed zero-dialog acceptance behavior is strictly bounded to the specific tested configuration (Loewe bild 5.65, chassis SL520, software version 6.7.9.0, with Mobile Control enabled), noting potential variation across chassis, firmware revisions, or network security configurations.
3. **Bilingual Documentation Synchronization**: English and Chinese versions of Section 6 are synchronized with semantic precision.
4. **Project Invariants Checked**: Frontend sources are unchanged. Page-copy equality and JavaScript syntax checks passed; the gate does not establish real BB10 compatibility. Full gate passed: `OK: project-gate (full, checks=8)`.

### Independent closure verification in this session

- Codex independently ran `./check.sh` on clean commit `62ef2494a94d70205e7eac16bf41b98bcf4d746e` before inspecting its diff. Result: `OK: project-gate (full, checks=8)`. The commit and clean source state remained unchanged after the check.
- The documentation fix is `b2526abc5c04b8015350c779c92680b5359cfba1`; `62ef249` records the author's handoff. From the previous independent report `f9d5f51`, only the two READMEs and two review reports changed; implementation, frontend, tests, build configuration, and gate configuration are unchanged.
- Checked the changed section 6 in English and the corresponding Chinese section. Both now describe the application's two SOAP actions rather than the TV's entire API surface, remove the exhaustive private-data assurance, and limit the reported acceptance observation to the identified device, firmware, and settings.
- R5 is closed after its first repair submission; unsuccessful repair submissions: 0. R1–R4 remain closed. The client configuration/documentation milestone closes within its third review round, with no outstanding findings.
- No real television was contacted in this review. The README's device observations are reported observations, not new independent hardware measurements. This approval covers the reported code/documentation findings and does not establish the entire TV API's security scope, production readiness, or BB10 device compatibility.
- The bilingual reports are committed as the review handoff. The existing 15-minute watch continues after approval until the user stops it.
