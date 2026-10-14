# Loewe Precision Web Remote

English | [简体中文](README_cn.md)

A high-performance, minimalist web remote control for Loewe OLED/LED TVs (chassis SL520, SL4xx, SL3xx) built with classical tactile aesthetics.

Designed with dual-tier device support:
1. **Modern Touchscreens**: Classical high-contrast physical D-Pad cross cluster with isolated center OK button, crisp visual active states, and native haptic vibration feedback.
2. **BlackBerry Passport (BB10 WebKit)**: Full support for the 1:1 square display (1440x1440), ES5 XMLHttpRequest compatibility, and physical hardware keyboard navigation without accidental confirmation triggers.

---

## 1. Key Features & Design

- **Classical High-Precision Physical D-Pad Cross Cluster**:
  - **Upper Section**: Tactile cross cluster with discrete `UP`, `DOWN`, `LEFT`, `RIGHT`, and an isolated central `OK` button. Navigation strictly emits direction codes without firing accidental confirmations.
  - **Lower Section**: Minimalist physical-style button grid with the essential golden keys:
    - `BACK` (Code 65)
    - `HOME` (Code 126, Sources & Main Hub)
    - `PLAY / PAUSE` (Code 53, Alphabet `l2700-hdr`)
    - `MENU` (Code 11)
    - `VOL -` (Code 20) / `VOL +` (Code 21)
    - `MUTE` (Code 13)
    - `WAKE` (UDP Port 9 Wake-on-LAN)
    - `STANDBY` (Code 12, Soft Standby preserving Wi-Fi)
- **BlackBerry Passport Tactile Hardware Keyboard Navigation**:
  - Full keyboard mapping enables blind operation without touching the screen:
    - `W` / `S` / `A` / `D` or Arrow Keys: Directional navigation (UP/DOWN/LEFT/RIGHT)
    - `Enter`: OK confirmation (exclusively fires OK, no overlap with direction keys)
    - `Space`: Home / Sources menu (mapped to Space to avoid BB10 browser's reserved `H` = History shortcut)
    - `B` / `Backspace` / `Esc`: Back
    - `P`: Play / Pause toggle
    - `M`: Menu
    - `+` / `-`: Volume control
  - **On-Screen Flash Feedback**: Pressing hardware keys lights up the corresponding on-screen buttons for instant visual confirmation.
- **Self-Healing Session State**:
  - Communicates over Loewe SOAP protocol (`urn:loewe.de:RemoteTV:Tablet`).
  - Automatically executes `RequestAccess` handshake upon token expiration or TV reboot.
  - Automatic multi-stage TV status sensing (TCP port 905, TCP port 2049, and ICMP Ping).
- **Two Independent Deployment Formats**:
  1. **Zero-Dependency Python Server** (`loewe_remote.py`): Runs directly using only Python 3 standard library.
  2. **High-Performance Rust Binary** (`target/release/loewe-web-remote`): Single standalone executable with compile-time embedded HTML/CSS/JS frontend.

---

## 2. Remote Key Specifications

| Action | Alphabet | Value | Protocol | Note / Passport Key |
|---|---|---|---|---|
| **UP** | `l2700` | `32` | SOAP InjectRCKey | D-Pad Up / `W` |
| **DOWN** | `l2700` | `33` | SOAP InjectRCKey | D-Pad Down / `S` |
| **LEFT** | `l2700` | `17` | SOAP InjectRCKey | D-Pad Left / `A` |
| **RIGHT** | `l2700` | `16` | SOAP InjectRCKey | D-Pad Right / `D` |
| **OK** | `l2700` | `38` | SOAP InjectRCKey | Center D-Pad / `Enter` |
| **BACK** | `l2700` | `65` | SOAP InjectRCKey | Return / `B` / `Backspace` |
| **HOME** | `l2700` | `126` | SOAP InjectRCKey | Sources & System Hub / `Space` |
| **PLAY/PAUSE** | `l2700-hdr` | `53` | SOAP InjectRCKey | Playback Toggle / `P` |
| **MENU** | `l2700` | `11` | SOAP InjectRCKey | System Settings / `M` |
| **VOL+** | `l2700` | `21` | SOAP InjectRCKey | Volume Increase / `+` |
| **VOL-** | `l2700` | `20` | SOAP InjectRCKey | Volume Decrease / `-` |
| **MUTE** | `l2700` | `13` | SOAP InjectRCKey | Mute Toggle |
| **STANDBY** | `l2700` | `12` | SOAP InjectRCKey | Soft Standby (Keeps Wi-Fi 3.3V) |
| **WAKE** | N/A | Magic Packet | UDP Port 9 | Wake-on-LAN Broadcast |

---

## 3. Quick Start

The server can run on any Linux host (PC, Raspberry Pi, NAS, or container) in the same local network as the television. Specify your Loewe TV's LAN IP and MAC address:

### Option A: Pure Python Server (Zero Dependencies)

```bash
# Run with TV IP and MAC parameters
python3 loewe_remote.py --tv-ip <TV_IP> --mac <TV_MAC> --port 8080

# Optional custom device name and UUID
python3 loewe_remote.py --tv-ip <TV_IP> --name "My-Remote"
```

### Option B: Standalone Rust Binary

```bash
# Build release binary
cargo build --release

# Run standalone binary with TV IP and MAC
./target/release/loewe-web-remote --tv-ip <TV_IP> --mac <TV_MAC> --port 8080

# Optional custom device name and UUID
./target/release/loewe-web-remote --tv-ip <TV_IP> --name "My-Remote"
```

Access the remote in any browser at:
`http://<SERVER_IP>:8080`

---

## 4. Verification and Testing

Install this clone's versioned Git hooks once:

```bash
./scripts/install-hooks.sh
```

Run the mechanical gate:

```bash
./check.sh --fast  # Before commits: syntax, format, build, lint, and page consistency.
./check.sh         # Before push/review/handoff: fast checks plus Rust and Python tests.
```

The pre-commit hook runs fast checks; pre-push runs full checks. The commit hook
requires all nonignored source changes staged, and the push hook checks a clean
HEAD only. They reject mismatched snapshots without stashing or changing source.
A new clone needs hook installation again; the author agent installs it through
project-gate. Hooks can be bypassed; this repository currently has no CI workflow.
Reviewers independently run the full gate on the actual review target.

Required tools: Bash, Git, Python 3, Node.js, and Rust with rustfmt/Clippy. Cargo
uses the tracked lockfile, runs offline, and stores gate artifacts separately in
`target/project-gate`. On a new machine, provision the Rust
dependencies separately with `cargo fetch --locked` before running the gate.
Successful runs print one line; failed runs print a bounded diagnostic and the
path to a complete temporary log.

Python checks use the standard library for syntax and indentation, without adding
runtime dependencies. Both page copies must match byte for byte. Node checks the
inline JavaScript syntax; ES5 compatibility and actual browser/device behavior
still require semantic/manual verification. Python formatting beyond indentation,
Python type checking, sanitizers, and dependency audits are not configured.
Full checks fail if either language discovers zero tests. Existing Python tests
use mocked TV transports and a local loopback HTTP server.

For a Python-only test run:

```bash
python3 -B test_remote.py -v
```

See [AGENTS.md](AGENTS.md) for author/reviewer rules.

## 5. Server Roles and Webpage Delivery

Python and Rust are two alternative, complete server implementations. Each serves the UI, exposes `/api/status`, `/api/key`, and `/api/wake`, manages TV sessions, sends SOAP commands, probes status, and sends Wake-on-LAN packets. Start one implementation for a deployment; both default to port 8080 and cannot share the same bind address and port.

| Component | Role | Delivered artifact / page source |
|---|---|---|
| Python | Standard-library server; run with Python 3. | `loewe_remote.py`, including the page in `HTML_CONTENT`. |
| Rust | Compiled server; Python is not required to run it. | `target/release/loewe-web-remote`, embedding `static/index.html` via `include_str!` at build time. |
| HTML/CSS/ES5 JavaScript | Browser layout, appearance, touch/keyboard events, and XHR API requests. | Equivalent page content served by either backend. |

The browser executes the page's JavaScript. The chosen server translates its API requests into television commands. Opening the HTML file alone does not provide the backend APIs.

The two page copies currently match, but there is no automatic synchronization step. Update both `static/index.html` and Python's `HTML_CONTENT` when changing the UI. Rebuild and restart Rust after changes to its embedded page; restart Python after changes to its script.

For review status and validation scope, see [CODE_REVIEW.md](CODE_REVIEW.md).
