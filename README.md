# Loewe Modern Minimalist Web Remote (Apple TV Siri Remote Style)

A high-performance, modern, minimalist web remote control for Loewe OLED/LED TVs (chassis SL520, SL4xx, SL3xx), styled after the Apple TV Siri Remote experience.

Designed with dual-tier device support:
1. **Modern Touchscreens**: Full Apple TV Clickpad experience with swipe gestures, center tap, and haptic vibration feedback.
2. **BlackBerry Passport (BB10 WebKit)**: Full support for the 1:1 square display (1440x1440), ES5 XMLHttpRequest compatibility, and physical capacitive keyboard blind navigation.

---

## 1. Key Features & Design

- **Apple TV Siri Remote Layout**:
  - **Upper Section**: Precision circular Touchpad supporting 4-way swipe navigation (Up, Down, Left, Right) and center-disc tap for OK confirmation.
  - **Lower Section**: Minimalist physical-style button grid with the essential golden keys:
    - `BACK` (Code 65)
    - `HOME` (Code 126, Sources & Main Hub)
    - `PLAY / PAUSE` (Code 53, Alphabet `l2700-hdr`)
    - `MENU` (Code 11)
    - `VOL -` (Code 20) / `VOL +` (Code 21)
    - `MUTE` (Code 13)
    - `WAKE` (UDP Port 9 Wake-on-LAN)
    - `STANDBY` (Code 12, Soft Standby preserving Wi-Fi)
- **BlackBerry Passport Physical Blind Navigation**:
  - Full keyboard mapping enables blind operation without touching the screen:
    - `W` / `S` / `A` / `D` or Arrow Keys: Directional navigation
    - `Enter` / `Space`: OK confirmation
    - `B` / `Backspace` / `Esc`: Back
    - `H`: Home / Sources
    - `M`: Menu
    - `P`: Play / Pause toggle
    - `+` / `-`: Volume control
- **Self-Healing Session State**:
  - Communicates over Loewe SOAP protocol (`urn:loewe.de:RemoteTV:Tablet`).
  - Automatically executes `RequestAccess` handshake upon token expiration or TV reboot.
  - Automatic multi-stage TV status sensing (TCP port 905, TCP port 2049, and ICMP Ping).
- **Two Independent Deployment Formats**:
  1. **Zero-Dependency Python Server** (`loewe_remote.py`): Runs directly using only Python 3 standard library.
  2. **High-Performance Rust Binary** (`target/release/loewe-web-remote`): Single standalone executable with compile-time embedded HTML/CSS/JS frontend.

---

## 2. Remote Key Specifications

| Action | Alphabet | Value | Protocol | Note |
|---|---|---|---|---|
| **UP** | `l2700` | `32` | SOAP InjectRCKey | Touchpad Swipe Up / `W` |
| **DOWN** | `l2700` | `33` | SOAP InjectRCKey | Touchpad Swipe Down / `S` |
| **LEFT** | `l2700` | `17` | SOAP InjectRCKey | Touchpad Swipe Left / `A` |
| **RIGHT** | `l2700` | `16` | SOAP InjectRCKey | Touchpad Swipe Right / `D` |
| **OK** | `l2700` | `38` | SOAP InjectRCKey | Touchpad Tap / `Enter` |
| **BACK** | `l2700` | `65` | SOAP InjectRCKey | Return / `B` |
| **HOME** | `l2700` | `126` | SOAP InjectRCKey | Sources & System Hub / `H` |
| **PLAY/PAUSE** | `l2700-hdr` | `53` | SOAP InjectRCKey | Playback Toggle / `P` |
| **MENU** | `l2700` | `11` | SOAP InjectRCKey | System Settings / `M` |
| **VOL+** | `l2700` | `21` | SOAP InjectRCKey | Volume Increase / `+` |
| **VOL-** | `l2700` | `20` | SOAP InjectRCKey | Volume Decrease / `-` |
| **MUTE** | `l2700` | `13` | SOAP InjectRCKey | Mute Toggle |
| **STANDBY** | `l2700` | `12` | SOAP InjectRCKey | Soft Standby (Keeps Wi-Fi 3.3V) |
| **WAKE** | N/A | Magic Packet | UDP Port 9 | Wake-on-LAN Broadcast |

---

## 3. Quick Start

### Option A: Pure Python Server (Zero Dependencies)

```bash
# Run with defaults (TV IP: 192.168.3.226, Port: 8080)
python3 loewe_remote.py

# Specify custom parameters
python3 loewe_remote.py --tv-ip 192.168.3.226 --mac f8:a2:d6:67:0f:f0 --port 8080
```

### Option B: Standalone Rust Binary

```bash
# Build release binary
cargo build --release

# Run standalone binary
./target/release/loewe-web-remote --tv-ip 192.168.3.226 --port 8080
```

Access the remote in any browser at:
`http://<SERVER_IP>:8080`

---

## 4. Verification and Testing

Execute the automated test suite:

```bash
python3 test_remote.py -v
```
