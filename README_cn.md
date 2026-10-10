# Loewe 现代极简 Web 遥控器（对标 Apple TV Siri Remote）

专为 Loewe 智能电视（SL520 / SL4xx / SL3xx 机芯系列）打造的高性能、极简独立开源 Web 遥控器。

具备双轨设备深度适配能力：
1. **现代智能手机**：全尺寸 Apple TV Clickpad 交互，支持滑动手势导航、中心点触确认以及触觉震动反馈（Haptic Vibration）。
2. **BlackBerry Passport (BB10 WebKit)**：完美适配 1:1 正方形 1440x1440 高清屏，坚持 ES5 XMLHttpRequest 规范，并原生捕获物理键盘滑动手势与按键实现无盲区物理盲操。

---

## 1. 核心设计与交互特色

- **Apple TV Siri Remote 交互架构**：
  - **上半区**：超大圆形 Touchpad 触控板，支持单指轻扫（Swipe）上下左右导航，中心圆盘单击（Tap）触发 OK 确认，自带微震动反馈。
  - **下半区**：双列极简物理键群（黄金按键集）：
    - `BACK`（返回，键码 65）
    - `HOME`（输入源与全局主页，键码 126）
    - `PLAY / PAUSE`（媒体播放/暂停，字典 `l2700-hdr`，键码 53）
    - `MENU`（设置菜单，键码 11）
    - `VOL -`（音量减，键码 20）/ `VOL +`（音量加，键码 21）
    - `MUTE`（静音，键码 13）
    - `WAKE`（UDP 端口 9 网络唤醒）
    - `STANDBY`（软待机关机，键码 12，保持 Wi-Fi 3.3V 待机供电）
- **BlackBerry Passport 物理键盘全盲操**：
  - 无需低头盯屏幕，直接使用 Passport 键盘实体键操控电视：
    - `W` / `S` / `A` / `D` 或 方向键：上下左右导航
    - `Enter` / `Space`：OK 确认
    - `B` / `Backspace` / `Esc`：返回
    - `H`：HOME 主页 / 信号源列表
    - `M`：菜单
    - `P`：播放 / 暂停切换
    - `+` / `-`：音量调节
- **自动状态自愈与网络探测**：
  - 原生支持 Loewe SOAP 协议（`urn:loewe.de:RemoteTV:Tablet`）。
  - 会话失效或电视重启时自动执行 `RequestAccess` 重新鉴权。
  - 具备 TCP 905、TCP 2049 与 ICMP Ping 三重毫秒级在线状态探测。
- **两种独立交付形态**：
  1. **零依赖纯 Python 单文件**（`loewe_remote.py`）：仅依赖 Python 3 标准库，随时随地单命令启动。
  2. **高性能 Rust 单二进制文件**（`target/release/loewe-web-remote`）：编译期内嵌完整静态前端资源，单文件免安装运行。

---

## 2. 遥控按键协议映射表

| 功能动作 | 字母字典 (Alphabet) | 键值 (Value) | 通信协议 | 说明与快捷映射 |
|---|---|---|---|---|
| **UP** | `l2700` | `32` | SOAP InjectRCKey | 触控板向上轻扫 / 键盘 `W` |
| **DOWN** | `l2700` | `33` | SOAP InjectRCKey | 触控板向下轻扫 / 键盘 `S` |
| **LEFT** | `l2700` | `17` | SOAP InjectRCKey | 触控板向左轻扫 / 键盘 `A` |
| **RIGHT** | `l2700` | `16` | SOAP InjectRCKey | 触控板向右轻扫 / 键盘 `D` |
| **OK** | `l2700` | `38` | SOAP InjectRCKey | 触控板中心轻触 / 键盘 `Enter` |
| **BACK** | `l2700` | `65` | SOAP InjectRCKey | 返回键 / 键盘 `B` |
| **HOME** | `l2700` | `126` | SOAP InjectRCKey | 信号源与主界面呼出 / 键盘 `H` |
| **PLAY/PAUSE** | `l2700-hdr` | `53` | SOAP InjectRCKey | 播放与暂停切换 / 键盘 `P` |
| **MENU** | `l2700` | `11` | SOAP InjectRCKey | 系统菜单 / 键盘 `M` |
| **VOL+** | `l2700` | `21` | SOAP InjectRCKey | 音量增加 / 键盘 `+` |
| **VOL-** | `l2700` | `20` | SOAP InjectRCKey | 音量减少 / 键盘 `-` |
| **MUTE** | `l2700` | `13` | SOAP InjectRCKey | 静音切换 |
| **STANDBY** | `l2700` | `12` | SOAP InjectRCKey | 软待机（保留 Wi-Fi 芯片 3.3V 供电） |
| **WAKE** | 无 | Magic Packet | UDP 端口 9 广播 | Wake-on-LAN 局域网唤醒 |

---

## 3. 快速启动指南

### 方案 A：纯 Python 单文件运行（免装依赖）

```bash
# 采用默认参数启动 (电视 IP: 192.168.3.226, 端口: 8080)
python3 loewe_remote.py

# 指定自定义参数
python3 loewe_remote.py --tv-ip 192.168.3.226 --mac f8:a2:d6:67:0f:f0 --port 8080
```

### 方案 B：独立静态编译 Rust 单二进制运行

```bash
# 构建优化发行包
cargo build --release

# 运行单二进制文件
./target/release/loewe-web-remote --tv-ip 192.168.3.226 --port 8080
```

启动后在任意手机、电脑或 BlackBerry Passport 浏览器中访问：
`http://<运行主机IP>:8080`

---

## 4. 自动化测试与验证

执行单元测试验证套件：

```bash
python3 test_remote.py -v
```
