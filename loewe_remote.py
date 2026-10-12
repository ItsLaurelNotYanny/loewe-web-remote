#!/usr/bin/env python3
"""Loewe Precision Web Remote.

Single-file server providing:
- Web remote control UI with tactile D-Pad cross cluster and minimal action buttons.
- BlackBerry Passport physical keyboard integration (W/A/S/D, Enter, Space, B, P, M, +/-).
- Zero accidental confirmation triggers (strict decoupling of navigation and OK).
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
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, minimum-scale=1, user-scalable=no, viewport-fit=cover">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>Loewe Remote</title>
    <style>
        * {
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
            -webkit-touch-callout: none;
            margin: 0;
            padding: 0;
        }

        html, body {
            width: 100%;
            height: 100%;
            min-height: 100%;
            margin: 0;
            padding: 0;
            background-color: #0a0a0c;
            color: #f5f5f7;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
            user-select: none;
            -webkit-user-select: none;
            touch-action: manipulation;
        }

        body {
            display: -webkit-box;
            display: -webkit-flex;
            display: flex;
            -webkit-box-orient: vertical;
            -webkit-box-direction: normal;
            -webkit-flex-direction: column;
            flex-direction: column;
            -webkit-box-pack: center;
            -webkit-justify-content: center;
            justify-content: center;
            -webkit-box-align: center;
            -webkit-align-items: center;
            align-items: center;
            padding: 8px;
            text-align: center;
            overflow-x: hidden;
            overflow-y: auto;
            box-sizing: border-box;
        }

        /* Remote Chassis: High Contrast, Solid Tactile Feel */
        .remote-frame {
            display: block;
            width: 100%;
            max-width: 360px;
            margin: auto;
            text-align: center;
            background: #16171b;
            background: linear-gradient(180deg, #1d1e23 0%, #131417 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 36px;
            padding: 16px 16px 18px 16px;
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.7);
            box-sizing: border-box;
        }

        /* Top Header: Brand & Status Pill */
        .header {
            width: 100%;
            display: -webkit-box;
            display: -webkit-flex;
            display: flex;
            -webkit-box-pack: justify;
            -webkit-justify-content: space-between;
            justify-content: space-between;
            -webkit-box-align: center;
            -webkit-align-items: center;
            align-items: center;
            padding: 0 6px;
            margin-bottom: 10px;
        }

        .brand-title {
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 3px;
            color: #86868b;
            text-transform: uppercase;
        }

        .status-pill {
            display: -webkit-inline-box;
            display: -webkit-inline-flex;
            display: inline-flex;
            -webkit-box-align: center;
            -webkit-align-items: center;
            align-items: center;
            gap: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            color: #86868b;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
        }

        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #86868b;
            display: inline-block;
            vertical-align: middle;
            margin-right: 4px;
        }

        .status-pill.online {
            background: rgba(48, 209, 88, 0.12);
            color: #30d158;
        }
        .status-pill.online .status-dot {
            background: #30d158;
            box-shadow: 0 0 8px #30d158;
        }

        .status-pill.standby {
            background: rgba(255, 69, 58, 0.12);
            color: #ff453a;
        }
        .status-pill.standby .status-dot {
            background: #ff453a;
        }

        /* Classical Physical D-Pad Cross Cluster */
        /* Bulletproof Native Block & Inline-Block Centering (No flexbox bugs) */
        .dpad-cluster {
            display: block;
            width: 100%;
            max-width: 320px;
            margin: 0 auto 12px auto;
            text-align: center;
            background: #1c1d22;
            padding: 14px 10px;
            border-radius: 28px;
            border: 1px solid rgba(255, 255, 255, 0.06);
            box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.6);
            box-sizing: border-box;
        }

        .dpad-row {
            display: block;
            width: 100%;
            margin: 0 auto 8px auto;
            text-align: center;
            white-space: nowrap;
            font-size: 0;
            line-height: 0;
        }

        .dpad-row:last-child {
            margin-bottom: 0;
        }

        .dpad-btn {
            display: inline-block;
            vertical-align: middle;
            width: 78px;
            height: 56px;
            line-height: 54px;
            margin: 0 4px;
            padding: 0;
            background: #25262d;
            color: #f5f5f7;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            font-size: 1.3rem;
            font-weight: 700;
            text-align: center;
            cursor: pointer;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.4);
            transition: background 0.1s, transform 0.08s;
            touch-action: manipulation;
            -webkit-appearance: none;
            appearance: none;
            box-sizing: border-box;
        }

        .dpad-btn:active, .dpad-btn.pressed {
            background: #3b82f6;
            color: #ffffff;
            -webkit-transform: scale(0.94);
            transform: scale(0.94);
        }

        .dpad-btn.btn-ok {
            background: #2563eb;
            color: #ffffff;
            font-size: 1.05rem;
            font-weight: 800;
            border-color: #3b82f6;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
        }

        .dpad-btn.btn-ok:active, .dpad-btn.btn-ok.pressed {
            background: #1d4ed8;
            -webkit-transform: scale(0.92);
            transform: scale(0.92);
        }

        /* Lower Section: 2-Column Physical Style Buttons (Flexbox for 100% BB10 compatibility) */
        .keypad-grid {
            width: 100%;
            display: -webkit-flex;
            display: flex;
            -webkit-flex-wrap: wrap;
            flex-wrap: wrap;
            -webkit-justify-content: space-between;
            justify-content: space-between;
            padding: 0 2px;
        }

        .remote-btn {
            width: 48%;
            margin-bottom: 10px;
            appearance: none;
            -webkit-appearance: none;
            background: #23242a;
            color: #f5f5f7;
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 18px;
            padding: 13px 8px;
            font-size: 0.9rem;
            font-weight: 600;
            display: -webkit-flex;
            display: flex;
            -webkit-align-items: center;
            align-items: center;
            -webkit-justify-content: center;
            justify-content: center;
            gap: 6px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.35);
            cursor: pointer;
            transition: background 0.12s, transform 0.08s;
            touch-action: manipulation;
        }

        .remote-btn:active, .remote-btn.pressed {
            background: #3a3b45;
            -webkit-transform: scale(0.95);
            transform: scale(0.95);
        }

        .remote-btn svg {
            width: 18px;
            height: 18px;
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
            width: 48%;
            display: -webkit-flex;
            display: flex;
            gap: 4px;
            margin-bottom: 10px;
        }

        .vol-rocker .remote-btn {
            width: 48%;
            margin-bottom: 0;
            padding: 13px 4px;
        }

        /* Passport Keyboard Legend */
        .keyboard-hint {
            font-size: 0.72rem;
            color: #86868b;
            text-align: center;
            line-height: 1.35;
            padding: 0 4px;
        }

        .keyboard-hint .badge-passport {
            color: #60a5fa;
            font-weight: 600;
        }

        .keyboard-hint kbd {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            padding: 1px 4px;
            font-family: monospace;
            font-size: 0.72rem;
            color: #d1d1d6;
        }

        /* Compact Adaptation for Passport 1440x1440 Square Display */
        @media (max-height: 700px), (max-width: 380px) {
            body { padding: 4px; }
            .remote-frame {
                padding: 12px 14px 14px 14px;
                gap: 8px;
                max-width: 340px;
                border-radius: 28px;
            }
            .header {
                margin-bottom: 4px;
            }
            .dpad-cluster {
                padding: 10px 8px;
                margin: 0 auto 8px auto;
                border-radius: 22px;
            }
            .dpad-row {
                margin: 0 auto 6px auto;
            }
            .dpad-btn {
                width: 72px;
                height: 50px;
                margin: 0 3px;
                font-size: 1.2rem;
                border-radius: 14px;
            }
            .dpad-btn.btn-ok {
                font-size: 0.95rem;
            }
            .remote-btn {
                padding: 11px 6px;
                font-size: 0.85rem;
                margin-bottom: 8px;
                border-radius: 14px;
            }
            .vol-rocker {
                margin-bottom: 8px;
            }
            .vol-rocker .remote-btn {
                padding: 11px 2px;
            }
        }
    </style>
</head>
<body>
    <main class="remote-frame" role="region" aria-label="Loewe Precision Web Remote">
        <!-- Top Status Bar -->
        <header class="header">
            <span class="brand-title">LOEWE</span>
            <div id="status-badge" class="status-pill" aria-live="polite">
                <span class="status-dot"></span>
                <span id="status-text">CONNECTING</span>
            </div>
        </header>

        <!-- Classical High-Precision Physical D-Pad Cross Cluster -->
        <section class="dpad-cluster" aria-label="Directional Navigation Pad">
            <div class="dpad-row">
                <button id="btn-up" class="dpad-btn" onclick="sendAction('key', '32', 'l2700')" title="Up (W)" aria-label="Up">&#9650;</button>
            </div>
            <div class="dpad-row">
                <button id="btn-left" class="dpad-btn" onclick="sendAction('key', '17', 'l2700')" title="Left (A)" aria-label="Left">&#9664;</button><button id="btn-ok" class="dpad-btn btn-ok" onclick="sendAction('key', '38', 'l2700')" title="OK Confirm (Enter)" aria-label="OK Confirm">OK</button><button id="btn-right" class="dpad-btn" onclick="sendAction('key', '16', 'l2700')" title="Right (D)" aria-label="Right">&#9654;</button>
            </div>
            <div class="dpad-row">
                <button id="btn-down" class="dpad-btn" onclick="sendAction('key', '33', 'l2700')" title="Down (S)" aria-label="Down">&#9660;</button>
            </div>
        </section>

        <!-- Lower Minimal Keypad (Golden Button Set) -->
        <section class="keypad-grid" aria-label="Remote Control Buttons">
            <!-- Row 1: Back (<) & Home (Sources / Home Menu) -->
            <button class="remote-btn" onclick="sendAction('key', '65', 'l2700')" title="Back / Return (B)" aria-label="Back">
                <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
                <span>BACK</span>
            </button>

            <button class="remote-btn btn-home" onclick="sendAction('key', '126', 'l2700')" title="Home / Sources Menu (Space)" aria-label="Home">
                <svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>
                <span>HOME</span>
            </button>

            <!-- Row 2: Play/Pause & Menu -->
            <button class="remote-btn" onclick="sendAction('key', '53', 'l2700-hdr')" title="Play / Pause (P)" aria-label="Play / Pause">
                <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z M14.5 19h2V5h-2v14z"/></svg>
                <span>PLAY</span>
            </button>

            <button class="remote-btn" onclick="sendAction('key', '11', 'l2700')" title="Menu Settings (M)" aria-label="Menu">
                <svg viewBox="0 0 24 24"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>
                <span>MENU</span>
            </button>

            <!-- Row 3: Volume Controls -->
            <div class="vol-rocker">
                <button class="remote-btn" onclick="sendAction('key', '20', 'l2700')" title="Volume Down (-)" aria-label="Volume Down">
                    <svg viewBox="0 0 24 24"><path d="M7 9v6h4l5 5V4l-5 5H7z"/></svg>
                    <span>-</span>
                </button>
                <button class="remote-btn" onclick="sendAction('key', '21', 'l2700')" title="Volume Up (+)" aria-label="Volume Up">
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

        <!-- Physical Keyboard Shortcuts Hint -->
        <footer class="keyboard-hint">
            <span class="badge-passport">Passport:</span> <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> Nav &bull; <kbd>Enter</kbd> OK &bull; <kbd>Space</kbd> Home &bull; <kbd>B</kbd> Back &bull; <kbd>P</kbd> Play
        </footer>
    </main>

    <script>
        // ES5 Pure JavaScript - 100% compatible with BB10 WebKit and modern smartphones
        var tvOnline = false;

        // Visual flash indicator helper for D-Pad buttons when triggered by physical keyboard
        function flashButton(btnId) {
            var el = document.getElementById(btnId);
            if (el) {
                el.className = el.className + ' pressed';
                setTimeout(function() {
                    el.className = el.className.replace(' pressed', '');
                }, 160);
            }
        }

        // Trigger native device haptic vibration if supported
        function hapticFeedback(pattern) {
            try {
                if (window.navigator && window.navigator.vibrate) {
                    window.navigator.vibrate(pattern || 15);
                }
            } catch (e) {}
        }

        // Prevent context menu popups and double-tap zoom gestures
        document.addEventListener('contextmenu', function(e) { e.preventDefault(); }, false);
        document.addEventListener('dblclick', function(e) { e.preventDefault(); }, false);

        // Generic XHR caller (ES5 compliant)
        function apiRequest(method, url, callback) {
            var xhr = new XMLHttpRequest();
            xhr.open(method, url, true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    var success = false;
                    if (xhr.status === 200) {
                        try {
                            var data = JSON.parse(xhr.responseText);
                            success = (data.success !== false);
                        } catch (e) {
                            success = true;
                        }
                    }
                    if (callback) {
                        callback(success, xhr.responseText);
                    }
                }
            };
            xhr.send();
        }

        // Visual error flash on failed action
        function flashError() {
            var badge = document.getElementById('status-badge');
            var text = document.getElementById('status-text');
            if (badge && text) {
                badge.className = 'status-pill standby';
                text.textContent = 'NO RESPONSE';
            }
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
                if (!ok) {
                    flashError();
                }
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

        // BLACKBERRY PASSPORT PHYSICAL KEYBOARD HANDLER
        // 100% Clean Mapping with Zero Accidental Confirms
        (function initKeyboardHandler() {
            function handleKeyDown(e) {
                var keyCode = e.keyCode || e.which;
                var key = (e.key ? e.key.toLowerCase() : String.fromCharCode(keyCode).toLowerCase());

                // 1. Navigation: W/A/S/D or Arrow Keys
                if (key === 'w' || key === 'arrowup' || keyCode === 38 || keyCode === 87) {
                    flashButton('btn-up');
                    sendAction('key', '32', 'l2700'); // Up ONLY
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
                if (key === 's' || key === 'arrowdown' || keyCode === 40 || keyCode === 83) {
                    flashButton('btn-down');
                    sendAction('key', '33', 'l2700'); // Down ONLY
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
                if (key === 'a' || key === 'arrowleft' || keyCode === 37 || keyCode === 65) {
                    flashButton('btn-left');
                    sendAction('key', '17', 'l2700'); // Left ONLY
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
                if (key === 'd' || key === 'arrowright' || keyCode === 39 || keyCode === 68) {
                    flashButton('btn-right');
                    sendAction('key', '16', 'l2700'); // Right ONLY
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }

                // 2. OK Confirm: Enter Key ONLY
                if (key === 'enter' || keyCode === 13) {
                    flashButton('btn-ok');
                    sendAction('key', '38', 'l2700'); // OK Confirm ONLY
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }

                // 3. HOME (Sources Menu): Space Bar (Avoids BB10 H=History)
                if (key === ' ' || key === 'space' || keyCode === 32 || key === 'i' || keyCode === 73) {
                    sendAction('key', '126', 'l2700'); // Home / Sources
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }

                // 4. BACK (Return): B / Backspace / Esc
                if (key === 'b' || key === 'backspace' || key === 'escape' || keyCode === 8 || keyCode === 27 || keyCode === 66) {
                    sendAction('key', '65', 'l2700'); // Back
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }

                // 5. PLAY / PAUSE: P
                if (key === 'p' || keyCode === 80) {
                    sendAction('key', '53', 'l2700-hdr'); // Play / Pause
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }

                // 6. MENU: M
                if (key === 'm' || keyCode === 77) {
                    sendAction('key', '11', 'l2700'); // Menu
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }

                // 7. VOLUME: + / -
                if (key === '+' || key === '=' || keyCode === 187 || keyCode === 61) {
                    sendAction('key', '21', 'l2700'); // Vol +
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
                if (key === '-' || key === '_' || keyCode === 189 || keyCode === 173) {
                    sendAction('key', '20', 'l2700'); // Vol -
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
            }

            // Capture phase prioritizes custom handlers before browser default
            window.addEventListener('keydown', handleKeyDown, true);
            document.addEventListener('keydown', handleKeyDown, true);
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
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
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
            if not code or not code.isdigit() or not (1 <= int(code) <= 9999):
                self._send_json({"success": False, "error": "Invalid key code: must be positive integer (1-9999)"}, status=400)
                return
            if alphabet not in ("l2700", "l2700-hdr"):
                self._send_json({"success": False, "error": "Invalid alphabet: allowed ['l2700', 'l2700-hdr']"}, status=400)
                return
            ok = self.controller.send_key(code, alphabet=alphabet)
            status_code = 200 if ok else 502
            self._send_json({"success": ok, "action": "key", "code": code, "alphabet": alphabet}, status=status_code)
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
