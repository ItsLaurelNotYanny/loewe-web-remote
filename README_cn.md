# Loewe 经典高精度 Web 遥控器

[English](README.md) | 简体中文

专为 Loewe 智能电视（SL520 / SL4xx / SL3xx 机芯系列）打造的高性能、极简独立开源 Web 遥控器，采用经典实体十字方向键（D-Pad）与黄金按键布局。

具备双轨设备深度适配能力：
1. **现代智能手机**：经典高对比度实体十字方向键群，独立的居中 OK 确认键，具备高响应度按压视觉动效与原生触觉微震反馈（Haptic Vibration）。
2. **BlackBerry Passport (BB10 WebKit)**：完美适配 1:1 正方形 1440x1440 高清屏，坚持 ES5 XMLHttpRequest 规范，并全面利用全键盘实体键进行精准盲操，彻底告别误触。

---

## 1. 核心设计与交互特色

- **经典高精度实体十字方向键群 (D-Pad)**：
  - **上半区**：采用经典十字按键布局，包含清晰独立的 `UP`、`DOWN`、`LEFT`、`RIGHT` 与居中 `OK` 键。方向操作仅发送方向码，完全与确认逻辑解耦，绝不触发误确认。
  - **下半区**：双列极简物理键群（黄金按键集）：
    - `BACK`（返回，键码 65）
    - `HOME`（输入源与全局主页，键码 126）
    - `PLAY / PAUSE`（媒体播放/暂停，字典 `l2700-hdr`，键码 53）
    - `MENU`（设置菜单，键码 11）
    - `VOL -`（音量减，键码 20）/ `VOL +`（音量加，键码 21）
    - `MUTE`（静音，键码 13）
    - `WAKE`（UDP 端口 9 网络唤醒）
    - `STANDBY`（软待机关机，键码 12，保持 Wi-Fi 3.3V 待机供电）
- **BlackBerry Passport 物理全键盘精准盲操**：
  - 彻底规避 BB10 浏览器内置系统快捷键冲突（例如系统保留 `H` 强制呼出历史记录）：
    - `W` / `S` / `A` / `D` 或 方向键：上下左右方向导航（单次按压仅移动焦点，绝不触发确认）
    - `Enter`：OK 确认（专有确认键）
    - `Space`（空格键）：HOME 主页 / 信号源列表（完美避开 BB10 `H` 键冲突）
    - `B` / `Backspace` / `Esc`：返回
    - `P`：播放 / 暂停切换
    - `M`：菜单
    - `+` / `-`：音量调节
  - **按键联动屏幕视觉高亮**：敲击实体键盘时，屏幕对应的 D-Pad 按键同步毫秒级高亮闪烁，提供清晰的视觉操作反馈。
- **自动状态自愈与网络探测**：
  - 原生支持 Loewe SOAP 协议（`urn:loewe.de:RemoteTV:Tablet`）。
  - 会话失效或电视重启时自动执行 `RequestAccess` 重新鉴权。
  - 具备 TCP 905、TCP 2049 与 ICMP Ping 三重毫秒级在线状态探测。
- **两种独立交付形态**：
  1. **零依赖纯 Python 单文件**（`loewe_remote.py`）：仅依赖 Python 3 标准库，随时随地单命令启动。
  2. **高性能 Rust 单二进制文件**（`target/release/loewe-web-remote`）：编译期内嵌完整静态前端资源，单文件免安装运行。

---

## 2. 遥控按键协议映射表

| 功能动作 | 字母字典 (Alphabet) | 键值 (Value) | 通信协议 | 说明与 Passport 实体键映射 |
|---|---|---|---|---|
| **UP** | `l2700` | `32` | SOAP InjectRCKey | 十字向上 / 键盘 `W` |
| **DOWN** | `l2700` | `33` | SOAP InjectRCKey | 十字向下 / 键盘 `S` |
| **LEFT** | `l2700` | `17` | SOAP InjectRCKey | 十字向左 / 键盘 `A` |
| **RIGHT** | `l2700` | `16` | SOAP InjectRCKey | 十字向右 / 键盘 `D` |
| **OK** | `l2700` | `38` | SOAP InjectRCKey | 中心确认 / 键盘 `Enter` |
| **BACK** | `l2700` | `65` | SOAP InjectRCKey | 返回键 / 键盘 `B` 或 `Backspace` |
| **HOME** | `l2700` | `126` | SOAP InjectRCKey | 信号源与主界面呼出 / 键盘 `Space` |
| **PLAY/PAUSE** | `l2700-hdr` | `53` | SOAP InjectRCKey | 播放与暂停切换 / 键盘 `P` |
| **MENU** | `l2700` | `11` | SOAP InjectRCKey | 系统菜单 / 键盘 `M` |
| **VOL+** | `l2700` | `21` | SOAP InjectRCKey | 音量增加 / 键盘 `+` |
| **VOL-** | `l2700` | `20` | SOAP InjectRCKey | 音量减少 / 键盘 `-` |
| **MUTE** | `l2700` | `13` | SOAP InjectRCKey | 静音切换 |
| **STANDBY** | `l2700` | `12` | SOAP InjectRCKey | 软待机（保留 Wi-Fi 芯片 3.3V 供电） |
| **WAKE** | 无 | Magic Packet | UDP 端口 9 广播 | Wake-on-LAN 局域网唤醒 |

---

## 3. 快速启动指南

服务端可运行在与电视处于同一局域网的任意 Linux 主机（PC、树莓派、NAS 或容器）上。请指定目标 Loewe 电视的局域网 IP 与 MAC 地址：

### 方案 A：纯 Python 单文件运行（免装依赖）

```bash
# 传入电视 IP 与 MAC 参数启动
python3 loewe_remote.py --tv-ip <TV_IP> --mac <TV_MAC> --port 8080

# 可选自定义配对设备名称
python3 loewe_remote.py --tv-ip <TV_IP> --name "My-Remote"
```

### 方案 B：独立 Rust 单二进制运行

```bash
# 构建优化发行包
cargo build --release

# 传入电视 IP 与 MAC 参数运行单二进制文件
./target/release/loewe-web-remote --tv-ip <TV_IP> --mac <TV_MAC> --port 8080

# 可选自定义配对设备名称
./target/release/loewe-web-remote --tv-ip <TV_IP> --name "My-Remote"
```

启动后在任意手机、电脑或 BlackBerry Passport 浏览器中访问：
`http://<SERVER_IP>:8080`

---

## 4. 验证与测试

为当前 clone 安装一次纳入版本管理的 Git hook：

```bash
./scripts/install-hooks.sh
```

运行机械检查 gate：

```bash
./check.sh --fast  # Before commits: syntax, format, build, lint, and page consistency.
./check.sh         # Before push/review/handoff: fast checks plus Rust and Python tests.
```

pre-commit 自动运行快档，pre-push 自动运行完整档。提交 hook 要求所有未忽略的源码改动已暂存；推送 hook 只检查干净的 HEAD。快照不一致时拒绝，不 stash、不修改源码。新 clone 需重新安装 hook，由作者 agent 通过 project-gate 安装。hook 可绕过；本仓库当前没有 CI 工作流。评审者须对实际目标独立运行完整 gate。

必需工具：Bash、Git、Python 3、Node.js，以及带 rustfmt/Clippy 的 Rust。Cargo 使用已跟踪的锁文件离线运行，gate 构建产物单独放在 `target/project-gate`；新机器先单独执行 `cargo fetch --locked` 准备 Rust 依赖。成功仅输出一行；失败输出截断诊断及完整临时日志路径。

Python 检查使用标准库验证语法和缩进，不添加运行时依赖。两份网页须逐字节一致。Node 验证内嵌 JavaScript 语法；ES5 兼容及真实浏览器/设备行为仍需语义/人工验证。超出缩进的 Python 格式化、Python 类型检查、sanitizer 和依赖 audit 尚未配置。完整档在任一语言发现零测试时失败。现有 Python 测试使用 mock 电视传输及本地回环 HTTP 服务。

仅运行 Python 测试：

```bash
python3 -B test_remote.py -v
```

作者/评审者规则见 [AGENTS_cn.md](AGENTS_cn.md)。

## 5. 服务端分工与网页交付

Python 和 Rust 是两套可供选择的完整服务端实现。每套都负责提供界面、暴露 `/api/status`、`/api/key` 和 `/api/wake`、管理电视会话、发送 SOAP 指令、探测状态及发送 Wake-on-LAN 数据包。一次部署启动其中一套即可；两套默认均使用 8080 端口，不能同时占用同一监听地址和端口。

| 组件 | 职责 | 交付文件 / 页面来源 |
|---|---|---|
| Python | 使用标准库的服务端，通过 Python 3 运行。 | `loewe_remote.py`，网页包含在 `HTML_CONTENT` 中。 |
| Rust | 编译后的服务端，运行时不需要 Python。 | `target/release/loewe-web-remote`，构建时通过 `include_str!` 嵌入 `static/index.html`。 |
| HTML/CSS/ES5 JavaScript | 浏览器布局、外观、触控/键盘事件及 XHR API 请求。 | 任一后端均提供相同的页面内容。 |

浏览器执行页面中的 JavaScript，所选服务端将页面发来的 API 请求转换为电视控制指令。单独打开 HTML 文件不会提供后端 API。

目前两份页面副本相同，但没有自动同步步骤。修改 UI 时，须同时更新 `static/index.html` 和 Python 的 `HTML_CONTENT`。修改 Rust 内嵌页面后须重新编译并重启；修改 Python 脚本后须重启服务。

评审状态及验证范围见 [CODE_REVIEW_cn.md](CODE_REVIEW_cn.md)。
