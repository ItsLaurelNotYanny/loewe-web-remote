#!/usr/bin/env python3
"""Loewe Modern Minimalist Web Remote (Apple TV Siri Remote Style).

Single-file server providing:
- Web remote control UI styled after Apple TV Siri Remote.
- Large gesture Touchpad with swipe and tap interactions and haptic feedback.
- BlackBerry Passport physical capacitive keyboard gesture and key support.
- Loewe SOAP remote protocol (InjectRCKey alphabet="l2700" & "l2700-hdr").
- Automatic session handshake and recovery (RequestAccess).
- ICMP & TCP TV reachability probing.
- Wake-on-WLAN UDP magic packet broadcast.
"""

import argparse
import binascii
import http.server
import json
import os
import re
import socket
import socketserver
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple

VERSION = "1.0.0"
DEFAULT_TV_IP = "192.168.3.226"
DEFAULT_MAC_ADDRESS = "f8:a2:d6:67:0f:f0"
DEFAULT_FCID = "2"
DEFAULT_CLIENT_UUID = "synology-ds220-loewe"
DEFAULT_DEVICE_NAME = "Synology-DS220"
BROADCAST_IP = "255.255.255.255"
WOL_PORT = 9

# Embedded Modern Minimalist HTML UI (Apple TV Siri Remote Design)
# Fully compatible with both modern mobile browsers and BB10 WebKit (ES5 XHR, Touch & Keyboard APIs)
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0, viewport-fit=cover">
    <title>Loewe Remote</title>
    <style>
        * {
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
            margin: 0;
            padding: 0;
        }

        :root {
            --bg-body: #0a0a0c;
            --remote-surface: #17181c;
            --touchpad-surface: #222329;
            --touchpad-active: #2b2c34;
            --touchpad-rim: #33343d;
            --button-surface: #23242a;
            --button-active: #3a3b45;
            --accent-standby: #e54d42;
            --text-primary: #f5f5f7;
            --text-muted: #86868b;
            --status-green: #30d158;
            --status-red: #ff453a;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
            background-color: var(--bg-body);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 12px;
            user-select: none;
            -webkit-user-select: none;
            touch-action: manipulation;
        }

        /* Remote Chassis: Apple TV Siri Remote Aluminum Unibody styling */
        .remote-frame {
            width: 100%;
            max-width: 370px;
            background: linear-gradient(180deg, #1f2025 0%, #151619 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 44px;
            padding: 22px 20px 26px 20px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7), inset 0 1px 0 rgba(255, 255, 255, 0.12);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 18px;
        }

        /* Top Header: Brand & Status Pill */
        .header {
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 8px;
        }

        .brand-title {
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 3px;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-muted);
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
        }

        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--text-muted);
        }

        .status-pill.online {
            background: rgba(48, 209, 88, 0.12);
            color: var(--status-green);
        }
        .status-pill.online .status-dot {
            background: var(--status-green);
            box-shadow: 0 0 8px var(--status-green);
        }

        .status-pill.standby {
            background: rgba(255, 69, 58, 0.12);
            color: var(--status-red);
        }
        .status-pill.standby .status-dot {
            background: var(--status-red);
        }

        /* Upper Section: Siri Remote Clickpad / Touch Surface */
        .clickpad-wrapper {
            position: relative;
            width: 240px;
            height: 240px;
            margin: 4px 0;
        }

        .touchpad {
            position: absolute;
            inset: 0;
            border-radius: 50%;
            background: radial-gradient(circle at 50% 35%, #2a2b32 0%, #1e1f24 100%);
            border: 2px solid var(--touchpad-rim);
            box-shadow: inset 0 3px 6px rgba(0, 0, 0, 0.6), 0 8px 24px rgba(0, 0, 0, 0.4);
            cursor: pointer;
            touch-action: none;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            transition: border-color 0.15s, background-color 0.15s, transform 0.1s;
        }

        .touchpad:active, .touchpad.active {
            border-color: #555765;
            transform: scale(0.985);
        }

        /* Directional Indicators on the Clickpad Ring */
        .arrow-hint {
            position: absolute;
            color: rgba(255, 255, 255, 0.3);
            font-size: 14px;
            font-weight: 800;
            pointer-events: none;
            transition: color 0.15s, transform 0.15s;
        }
        .arrow-hint.hint-up    { top: 10px; }
        .arrow-hint.hint-down  { bottom: 10px; }
        .arrow-hint.hint-left  { left: 12px; }
        .arrow-hint.hint-right { right: 12px; }

        .arrow-hint.active {
            color: #ffffff;
            transform: scale(1.3);
        }

        /* Inner Center OK Disc */
        .center-button {
            width: 90px;
            height: 90px;
            border-radius: 50%;
            background: linear-gradient(145deg, #282930, #1c1d22);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            pointer-events: none;
            transition: transform 0.1s, background 0.15s;
        }

        .center-label {
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: #ffffff;
        }

        .center-sublabel {
            font-size: 0.6rem;
            color: var(--text-muted);
            letter-spacing: 0.5px;
            margin-top: 1px;
            text-transform: uppercase;
        }

        .center-button.pressed {
            transform: scale(0.92);
            background: linear-gradient(145deg, #353640, #222329);
        }

        /* Lower Section: 2-Column Physical Style Buttons (Apple TV Grid) */
        .keypad-grid {
            width: 100%;
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-gap: 14px 16px;
            padding: 4px 6px;
        }

        .remote-btn {
            appearance: none;
            -webkit-appearance: none;
            background: var(--button-surface);
            color: var(--text-primary);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 20px;
            padding: 16px 12px;
            font-size: 0.95rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08);
            cursor: pointer;
            transition: background 0.12s, transform 0.08s, box-shadow 0.12s;
            touch-action: manipulation;
        }

        .remote-btn:active, .remote-btn.pressed {
            background: var(--button-active);
            transform: scale(0.95);
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
        }

        .remote-btn svg {
            width: 20px;
            height: 20px;
            fill: currentColor;
            flex-shrink: 0;
        }

        /* Accent & Power Key Variations */
        .remote-btn.btn-home {
            color: #ffffff;
        }

        .remote-btn.btn-standby {
            color: #ffb4ab;
        }
        .remote-btn.btn-standby:active, .remote-btn.btn-standby.pressed {
            background: #4a1515;
            color: #ffffff;
        }

        .remote-btn.btn-wake {
            color: #72f29b;
        }
        .remote-btn.btn-wake:active, .remote-btn.btn-wake.pressed {
            background: #144026;
            color: #ffffff;
        }

        /* Volume Rocker Group */
        .vol-rocker {
            display: flex;
            gap: 6px;
            width: 100%;
        }

        .vol-rocker .remote-btn {
            flex: 1;
            padding: 16px 6px;
        }

        /* Helper info banner for Passport Keyboard */
        .keyboard-hint {
            font-size: 0.72rem;
            color: var(--text-muted);
            text-align: center;
            line-height: 1.4;
            padding: 0 10px;
        }

        .keyboard-hint kbd {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            padding: 1px 5px;
            font-family: monospace;
            font-size: 0.75rem;
            color: #d1d1d6;
        }

        /* Responsive adaptation for Passport 1440x1440 / Small displays */
        @media (max-height: 600px), (max-width: 360px) {
            .remote-frame {
                padding: 14px 14px 16px 14px;
                gap: 12px;
                max-width: 330px;
            }
            .clickpad-wrapper {
                width: 200px;
                height: 200px;
            }
            .center-button {
                width: 76px;
                height: 76px;
            }
            .remote-btn {
                padding: 13px 8px;
                font-size: 0.85rem;
            }
            .keypad-grid {
                grid-gap: 10px 12px;
            }
        }
    </style>
</head>
<body>
    <main class="remote-frame" role="region" aria-label="Loewe Apple TV Style Remote">
        <!-- Top Status Bar -->
        <header class="header">
            <span class="brand-title">LOEWE</span>
            <div id="status-badge" class="status-pill" aria-live="polite">
                <span class="status-dot"></span>
                <span id="status-text">CONNECTING</span>
            </div>
        </header>

        <!-- Siri Remote Gesture Touchpad / Clickpad -->
        <section class="clickpad-wrapper" aria-label="Touch Navigation Area">
            <div id="touchpad" class="touchpad" role="button" tabindex="0" aria-label="Navigation Touchpad">
                <span id="hint-up" class="arrow-hint hint-up">&#9650;</span>
                <span id="hint-down" class="arrow-hint hint-down">&#9660;</span>
                <span id="hint-left" class="arrow-hint hint-left">&#9664;</span>
                <span id="hint-right" class="arrow-hint hint-right">&#9654;</span>

                <div id="center-disc" class="center-button">
                    <span class="center-label">OK</span>
                    <span class="center-sublabel">TAP / SWIPE</span>
                </div>
            </div>
        </section>

        <!-- Lower Minimal Keypad (Golden Button Set) -->
        <section class="keypad-grid" aria-label="Remote Control Buttons">
            <!-- Row 1: Back (<) & Home (Sources / Home Menu) -->
            <button class="remote-btn" onclick="sendAction('key', '65', 'l2700')" title="Back / Return" aria-label="Back">
                <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
                <span>BACK</span>
            </button>

            <button class="remote-btn btn-home" onclick="sendAction('key', '126', 'l2700')" title="Home / Sources Menu" aria-label="Home">
                <svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>
                <span>HOME</span>
            </button>

            <!-- Row 2: Play/Pause & TV Mode -->
            <button class="remote-btn" onclick="sendAction('key', '53', 'l2700-hdr')" title="Play / Pause" aria-label="Play / Pause">
                <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z M14.5 19h2V5h-2v14z"/></svg>
                <span>PLAY</span>
            </button>

            <button class="remote-btn" onclick="sendAction('key', '11', 'l2700')" title="Menu Settings" aria-label="Menu">
                <svg viewBox="0 0 24 24"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>
                <span>MENU</span>
            </button>

            <!-- Row 3: Volume Controls -->
            <div class="vol-rocker">
                <button class="remote-btn" onclick="sendAction('key', '20', 'l2700')" title="Volume Down" aria-label="Volume Down">
                    <svg viewBox="0 0 24 24"><path d="M7 9v6h4l5 5V4l-5 5H7z"/></svg>
                    <span>-</span>
                </button>
                <button class="remote-btn" onclick="sendAction('key', '21', 'l2700')" title="Volume Up" aria-label="Volume Up">
                    <svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>
                    <span>+</span>
                </button>
            </div>

            <button class="remote-btn" onclick="sendAction('key', '13', 'l2700')" title="Mute Audio" aria-label="Mute Audio">
                <svg viewBox="0 0 24 24"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/></svg>
                <span>MUTE</span>
            </button>

            <!-- Row 4: Power Controls (Wake / Standby) -->
            <button class="remote-btn btn-wake" onclick="sendAction('wake')" title="Wake-on-LAN" aria-label="Wake TV">
                <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 14h-2v-2h2v2zm0-4h-2V7h2v5z"/></svg>
                <span>WAKE</span>
            </button>

            <button class="remote-btn btn-standby" onclick="sendAction('key', '12', 'l2700')" title="Soft Standby" aria-label="Standby TV">
                <svg viewBox="0 0 24 24"><path d="M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42A7.92 7.92 0 0 1 20 12c0 4.42-3.58 8-8 8s-8-3.58-8-8c0-2.47 1.12-4.67 2.89-6.14l-1.42-1.42C3.21 6.39 2 9.05 2 12c0 5.52 4.48 10 10 10s10-4.48 10-10c0-2.95-1.21-5.61-3.17-7.83z"/></svg>
                <span>STANDBY</span>
            </button>
        </section>

        <!-- Physical Keyboard Shortcuts Hint (Passport Blind Operation) -->
        <footer class="keyboard-hint">
            Passport / PC: <kbd>W</kbd>/<kbd>S</kbd>/<kbd>A</kbd>/<kbd>D</kbd> or Arrows &bull; <kbd>Enter</kbd>/<kbd>Space</kbd> OK &bull; <kbd>H</kbd> Home &bull; <kbd>B</kbd> Back
        </footer>
    </main>

    <script>
        // ES5 Pure JavaScript - 100% compatible with BB10 WebKit and modern smartphones
        var tvOnline = false;

        // Trigger native device haptic vibration if supported
        function hapticFeedback(pattern) {
            try {
                if (window.navigator && window.navigator.vibrate) {
                    window.navigator.vibrate(pattern || 15);
                }
            } catch (e) {}
        }

        // Generic XHR caller (ES5 compliant, avoid fetch API for BB10 WebKit)
        function apiRequest(method, url, callback) {
            var xhr = new XMLHttpRequest();
            xhr.open(method, url, true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    if (callback) {
                        callback(xhr.status === 200, xhr.responseText);
                    }
                }
            };
            xhr.send();
        }

        // Send remote button action
        function sendAction(action, code, alphabet) {
            hapticFeedback(20);
            var url = '/api/' + action;
            if (code) {
                url += '?code=' + encodeURIComponent(code);
                if (alphabet) {
                    url += '&alphabet=' + encodeURIComponent(alphabet);
                }
            }
            apiRequest('POST', url, function(ok) {
                setTimeout(fetchStatus, 1500);
            });
        }

        // Update TV Status Indicator
        function fetchStatus() {
            apiRequest('GET', '/api/status', function(ok, resp) {
                var badge = document.getElementById('status-badge');
                var text = document.getElementById('status-text');
                if (ok) {
                    try {
                        var data = JSON.parse(resp);
                        if (data.status === 'on') {
                            tvOnline = true;
                            badge.className = 'status-pill online';
                            text.textContent = 'ONLINE';
                            return;
                        }
                    } catch (e) {}
                }
                tvOnline = false;
                badge.className = 'status-pill standby';
                text.textContent = 'STANDBY';
            });
        }

        // Touchpad Gestures: Tap for OK, Swipe for Up/Down/Left/Right
        (function initTouchpad() {
            var pad = document.getElementById('touchpad');
            var disc = document.getElementById('center-disc');
            var hintUp = document.getElementById('hint-up');
            var hintDown = document.getElementById('hint-down');
            var hintLeft = document.getElementById('hint-left');
            var hintRight = document.getElementById('hint-right');

            var startX = 0, startY = 0;
            var startTime = 0;
            var isTracking = false;
            var hasSwiped = false;
            var SWIPE_THRESHOLD = 26; // pixels

            function clearHints() {
                hintUp.className = 'arrow-hint hint-up';
                hintDown.className = 'arrow-hint hint-down';
                hintLeft.className = 'arrow-hint hint-left';
                hintRight.className = 'arrow-hint hint-right';
            }

            function handleStart(x, y) {
                isTracking = true;
                hasSwiped = false;
                startX = x;
                startY = y;
                startTime = new Date().getTime();
                pad.className = 'touchpad active';
                disc.className = 'center-button pressed';
            }

            function handleMove(x, y, evt) {
                if (!isTracking) return;
                var dx = x - startX;
                var dy = y - startY;

                if (!hasSwiped) {
                    if (Math.abs(dx) > SWIPE_THRESHOLD || Math.abs(dy) > SWIPE_THRESHOLD) {
                        hasSwiped = true;
                        if (evt && evt.preventDefault) evt.preventDefault();

                        if (Math.abs(dx) > Math.abs(dy)) {
                            if (dx > 0) {
                                // Swipe Right -> Key 16
                                hintRight.className = 'arrow-hint hint-right active';
                                sendAction('key', '16', 'l2700');
                            } else {
                                // Swipe Left -> Key 17
                                hintLeft.className = 'arrow-hint hint-left active';
                                sendAction('key', '17', 'l2700');
                            }
                        } else {
                            if (dy > 0) {
                                // Swipe Down -> Key 33
                                hintDown.className = 'arrow-hint hint-down active';
                                sendAction('key', '33', 'l2700');
                            } else {
                                // Swipe Up -> Key 32
                                hintUp.className = 'arrow-hint hint-up active';
                                sendAction('key', '32', 'l2700');
                            }
                        }
                    }
                }
            }

            function handleEnd() {
                if (!isTracking) return;
                isTracking = false;
                pad.className = 'touchpad';
                disc.className = 'center-button';
                setTimeout(clearHints, 200);

                var elapsed = new Date().getTime() - startTime;
                if (!hasSwiped && elapsed < 500) {
                    // Tap -> OK Key 38
                    sendAction('key', '38', 'l2700');
                }
            }

            // Touch events
            pad.addEventListener('touchstart', function(e) {
                if (e.touches.length === 1) {
                    handleStart(e.touches[0].clientX, e.touches[0].clientY);
                }
            }, false);

            pad.addEventListener('touchmove', function(e) {
                if (e.touches.length === 1) {
                    handleMove(e.touches[0].clientX, e.touches[0].clientY, e);
                }
            }, false);

            pad.addEventListener('touchend', function() { handleEnd(); }, false);
            pad.addEventListener('touchcancel', function() { handleEnd(); }, false);

            // Mouse fallback for desktop testing
            pad.addEventListener('mousedown', function(e) {
                handleStart(e.clientX, e.clientY);
            });
            window.addEventListener('mousemove', function(e) {
                handleMove(e.clientX, e.clientY, e);
            });
            window.addEventListener('mouseup', function() {
                handleEnd();
            });
        })();

        // BlackBerry Passport Physical Keyboard & PC Blind Operation Support
        (function initKeyboardHandler() {
            window.addEventListener('keydown', function(e) {
                var key = e.key ? e.key.toLowerCase() : '';
                var keyCode = e.keyCode || e.which;

                // Handle Navigation
                if (key === 'arrowup' || key === 'w' || keyCode === 38) {
                    sendAction('key', '32', 'l2700'); // Up
                    e.preventDefault();
                } else if (key === 'arrowdown' || key === 's' || keyCode === 40) {
                    sendAction('key', '33', 'l2700'); // Down
                    e.preventDefault();
                } else if (key === 'arrowleft' || key === 'a' || keyCode === 37) {
                    sendAction('key', '17', 'l2700'); // Left
                    e.preventDefault();
                } else if (key === 'arrowright' || key === 'd' || keyCode === 39) {
                    sendAction('key', '16', 'l2700'); // Right
                    e.preventDefault();
                } else if (key === 'enter' || key === ' ' || keyCode === 13 || keyCode === 32) {
                    sendAction('key', '38', 'l2700'); // OK
                    e.preventDefault();
                } else if (key === 'escape' || key === 'backspace' || key === 'b' || keyCode === 8 || keyCode === 27) {
                    sendAction('key', '65', 'l2700'); // Back
                    e.preventDefault();
                } else if (key === 'h') {
                    sendAction('key', '126', 'l2700'); // Home / Sources
                    e.preventDefault();
                } else if (key === 'm') {
                    sendAction('key', '11', 'l2700'); // Menu
                    e.preventDefault();
                } else if (key === 'p') {
                    sendAction('key', '53', 'l2700-hdr'); // Play / Pause
                    e.preventDefault();
                } else if (key === '+' || key === '=') {
                    sendAction('key', '21', 'l2700'); // Vol +
                    e.preventDefault();
                } else if (key === '-' || key === '_') {
                    sendAction('key', '20', 'l2700'); // Vol -
                    e.preventDefault();
                }
            });
        })();

        // Polling loop for TV online status (every 4 seconds)
        fetchStatus();
        setInterval(fetchStatus, 4000);
    </script>
</body>
</html>
"""


class LoeweController:
    """Handles communication with Loewe TV using SOAP and UDP Wake-on-LAN."""

    def __init__(
        self,
        tv_ip: str = DEFAULT_TV_IP,
        mac_address: str = DEFAULT_MAC_ADDRESS,
        client_uuid: str = DEFAULT_CLIENT_UUID,
        device_name: str = DEFAULT_DEVICE_NAME,
        fcid: str = DEFAULT_FCID,
    ):
        self.tv_ip = tv_ip
        self.mac_address = mac_address
        self.client_uuid = client_uuid
        self.device_name = device_name
        self.fcid = fcid
        self.client_id: Optional[str] = None
        self._lock = threading.Lock()

    def wake_on_lan(self, broadcast_ip: str = BROADCAST_IP, port: int = WOL_PORT) -> bool:
        """Sends a standard UDP Wake-on-LAN magic packet."""
        mac_clean = self.mac_address.replace(":", "").replace("-", "").strip()
        mac_bytes = binascii.unhexlify(mac_clean)
        magic_packet = b"\xff" * 6 + mac_bytes * 16

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            targets = [broadcast_ip]
            # If TV IP is known, calculate subnet broadcast target
            ip_parts = self.tv_ip.split(".")
            if len(ip_parts) == 4:
                targets.append(f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255")

            success = False
            for target in targets:
                try:
                    sock.sendto(magic_packet, (target, port))
                    success = True
                except Exception:
                    pass
            return success

    def probe_status(self) -> Dict[str, str]:
        """Probes whether TV is responsive via TCP port 905/2049 or ICMP."""
        # 1. Fast TCP probe on SOAP port 905
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.35)
                if s.connect_ex((self.tv_ip, 905)) == 0:
                    return {"status": "on", "method": "tcp:905"}
        except Exception:
            pass

        # 2. Fast TCP probe on port 2049 (NFS)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.35)
                if s.connect_ex((self.tv_ip, 2049)) == 0:
                    return {"status": "on", "method": "tcp:2049"}
        except Exception:
            pass

        # 3. ICMP Ping check
        try:
            cmd = ["ping", "-c", "1", "-W", "1", self.tv_ip]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return {"status": "on", "method": "icmp"}
        except Exception:
            pass

        return {"status": "off", "method": "none"}

    def _soap_request(self, action: str, body_xml: str, timeout: float = 2.5) -> bytes:
        """Executes a SOAP HTTP POST to the TV endpoint."""
        payload = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <m:{action} xmlns:m="urn:loewe.de:RemoteTV:Tablet">
      {body_xml}
    </m:{action}>
  </s:Body>
</s:Envelope>"""

        req = urllib.request.Request(
            f"http://{self.tv_ip}:905/loewe_tablet_0001",
            data=payload.encode("utf-8"),
            headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPACTION": f'"urn:loewe.de:RemoteTV:Tablet#{action}"',
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()

    def request_access(self) -> Tuple[Optional[str], str, Optional[str]]:
        """Executes RequestAccess to obtain an authenticated ClientId."""
        body = f"""<m:fcid>0</m:fcid>
      <m:DeviceType>Tablet</m:DeviceType>
      <m:DeviceName>{self.device_name}</m:DeviceName>
      <m:DeviceUUID>{self.client_uuid}</m:DeviceUUID>
      <m:RequesterName>{self.device_name}</m:RequesterName>"""

        xml_data = self._soap_request("RequestAccess", body)
        text = xml_data.decode("utf-8", errors="ignore")

        cid_match = re.search(r"<m:ClientId>(.*?)</m:ClientId>", text)
        fcid_match = re.search(r"<m:fcid>(.*?)</m:fcid>", text)
        status_match = re.search(r"<m:AccessStatus>(.*?)</m:AccessStatus>", text)

        client_id = cid_match.group(1) if cid_match else None
        fcid = fcid_match.group(1) if fcid_match else "0"
        status = status_match.group(1) if status_match else None

        with self._lock:
            self.client_id = client_id
            self.fcid = fcid

        return client_id, fcid, status

    def send_key(self, key_code: str, alphabet: str = "l2700") -> bool:
        """Injects remote key press/release sequence, auto-negotiating session if needed."""
        with self._lock:
            client_id = self.client_id
            fcid = self.fcid

        if not client_id:
            client_id, fcid, _ = self.request_access()
            if not client_id:
                return False

        def _do_inject(c_id: str, f_id: str) -> bytes:
            body = f"""<m:fcid>{f_id}</m:fcid>
      <m:ClientId>{c_id}</m:ClientId>
      <m:InputEventSequence>
        <m:RCKeyEvent alphabet="{alphabet}" mode="press" value="{key_code}"/>
        <m:RCKeyEvent alphabet="{alphabet}" mode="release" value="{key_code}"/>
      </m:InputEventSequence>"""
            return self._soap_request("InjectRCKey", body)

        try:
            resp = _do_inject(client_id, fcid).decode("utf-8", errors="ignore")
            # If response indicates invalid session, reconnect
            if "INVALID" in resp or "<m:ClientId>" not in resp:
                raise ValueError("Session token invalid or rejected")
            return True
        except Exception:
            # Re-negotiate session once on failure
            try:
                new_cid, new_fcid, _ = self.request_access()
                if new_cid:
                    _do_inject(new_cid, new_fcid)
                    return True
            except Exception:
                pass
            return False


class RemoteRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler serving the modern remote web UI and API endpoints."""

    controller: LoeweController

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode("utf-8"))
        elif url.path == "/api/status":
            st = self.controller.probe_status()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(st).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)

        if url.path == "/api/wake":
            ok = self.controller.wake_on_lan()
            self._send_json({"success": ok, "action": "wake"})
        elif url.path == "/api/key":
            code = query.get("code", [None])[0]
            alphabet = query.get("alphabet", ["l2700"])[0]
            if not code:
                self._send_json({"success": False, "error": "Missing key code"}, status=400)
                return
            ok = self.controller.send_key(code, alphabet=alphabet)
            self._send_json({"success": ok, "action": "key", "code": code, "alphabet": alphabet})
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        # Clean logging for stdout
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    parser = argparse.ArgumentParser(description="Loewe TV Modern Web Remote")
    parser.add_argument("--tv-ip", default=DEFAULT_TV_IP, help=f"Loewe TV IP address (default: {DEFAULT_TV_IP})")
    parser.add_argument("--mac", default=DEFAULT_MAC_ADDRESS, help=f"Loewe TV MAC address (default: {DEFAULT_MAC_ADDRESS})")
    parser.add_argument("--port", type=int, default=8080, help="Web server port (default: 8080)")
    parser.add_argument("--bind", default="0.0.0.0", help="Web server bind address (default: 0.0.0.0)")
    args = parser.parse_args()

    controller = LoeweController(
        tv_ip=args.tv_ip,
        mac_address=args.mac,
    )

    class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    RemoteRequestHandler.controller = controller
    server = ThreadedServer((args.bind, args.port), RemoteRequestHandler)

    print(f"=== Loewe Web Remote v{VERSION} ===")
    print(f"TV Target : {args.tv_ip} (MAC: {args.mac})")
    print(f"Listening : http://{args.bind}:{args.port}")
    print("Press Ctrl+C to terminate.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        server.server_close()


if __name__ == "__main__":
    main()
