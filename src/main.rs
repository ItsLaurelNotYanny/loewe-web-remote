//! Precision Web Remote for Loewe TV
//! Single-binary web server written in Rust with embedded HTML/CSS/JS frontend.

use axum::{
    extract::{Query, State},
    http::{header, StatusCode},
    response::{Html, IntoResponse},
    routing::{get, post},
    Json, Router,
};
use clap::Parser;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::net::{SocketAddr, TcpStream, UdpSocket};
use std::process::Command;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Mutex;
use tower_http::cors::CorsLayer;
use tracing::{info, warn};

pub const DEFAULT_TV_IP: &str = "192.168.3.226";
pub const DEFAULT_MAC_ADDRESS: &str = "f8:a2:d6:67:0f:f0";
pub const DEFAULT_FCID: &str = "2";
pub const DEFAULT_CLIENT_UUID: &str = "loewe-web-remote";
pub const DEFAULT_DEVICE_NAME: &str = "Loewe-Web-Remote";
pub const BROADCAST_IP: &str = "255.255.255.255";
pub const WOL_PORT: u16 = 9;

// Compile-time embedded static HTML UI
pub const EMBEDDED_HTML: &str = include_str!("../static/index.html");

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
pub struct CliArgs {
    #[arg(long, default_value = DEFAULT_TV_IP, help = "Loewe TV IP address")]
    pub tv_ip: String,

    #[arg(long, default_value = DEFAULT_MAC_ADDRESS, help = "Loewe TV MAC address")]
    pub mac: String,

    #[arg(long, default_value_t = 8080, help = "Web server port")]
    pub port: u16,

    #[arg(long, default_value = "0.0.0.0", help = "Web server bind address")]
    pub bind: String,

    #[arg(
        long,
        help = "Client device name displayed on TV screen during pairing"
    )]
    pub name: Option<String>,

    #[arg(long, help = "Client UUID used for TV pairing registration")]
    pub uuid: Option<String>,
}

#[derive(Clone)]
pub struct AppState {
    pub tv_ip: String,
    pub mac_address: String,
    pub client_uuid: String,
    pub device_name: String,
    pub session: Arc<Mutex<SessionInfo>>,
    pub http_client: reqwest::Client,
}

#[derive(Default, Clone, Debug)]
pub struct SessionInfo {
    pub client_id: Option<String>,
    pub fcid: String,
}

#[derive(Serialize)]
pub struct StatusResponse {
    pub status: String,
    pub method: String,
}

#[derive(Deserialize)]
pub struct KeyParams {
    pub code: String,
    #[serde(default = "default_alphabet")]
    pub alphabet: String,
}

impl KeyParams {
    pub fn validate(&self) -> Result<(u32, &str), &'static str> {
        let code_num = self
            .code
            .trim()
            .parse::<u32>()
            .map_err(|_| "Invalid key code: must be numeric")?;
        if code_num == 0 || code_num > 9999 {
            return Err("Key code out of valid range (1..9999)");
        }
        match self.alphabet.as_str() {
            "l2700" | "l2700-hdr" => Ok((code_num, self.alphabet.as_str())),
            _ => Err("Invalid alphabet: must be 'l2700' or 'l2700-hdr'"),
        }
    }
}

fn default_alphabet() -> String {
    "l2700".to_string()
}

#[derive(Serialize)]
pub struct ActionResponse {
    pub success: bool,
    pub action: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub alphabet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

pub fn wake_on_lan(mac: &str, tv_ip: &str) -> bool {
    let clean = mac.replace([':', '-'], "");
    let mac_bytes = match hex::decode(clean) {
        Ok(b) if b.len() == 6 => b,
        _ => return false,
    };

    let mut packet = vec![0xFFu8; 6];
    for _ in 0..16 {
        packet.extend_from_slice(&mac_bytes);
    }

    let socket = match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = socket.set_broadcast(true);

    let mut targets = vec![format!("{}:{}", BROADCAST_IP, WOL_PORT)];
    let parts: Vec<&str> = tv_ip.split('.').collect();
    if parts.len() == 4 {
        targets.push(format!(
            "{}.{}.{}.255:{}",
            parts[0], parts[1], parts[2], WOL_PORT
        ));
    }

    let mut sent = false;
    for target in targets {
        if socket.send_to(&packet, &target).is_ok() {
            sent = true;
        }
    }
    sent
}

pub fn probe_tv_status(tv_ip: &str) -> StatusResponse {
    // 1. TCP 905 probe
    if let Ok(addr) = format!("{}:905", tv_ip).parse::<SocketAddr>() {
        if TcpStream::connect_timeout(&addr, Duration::from_millis(350)).is_ok() {
            return StatusResponse {
                status: "on".to_string(),
                method: "tcp:905".to_string(),
            };
        }
    }

    // 2. TCP 2049 probe (NFS)
    if let Ok(addr) = format!("{}:2049", tv_ip).parse::<SocketAddr>() {
        if TcpStream::connect_timeout(&addr, Duration::from_millis(350)).is_ok() {
            return StatusResponse {
                status: "on".to_string(),
                method: "tcp:2049".to_string(),
            };
        }
    }

    // 3. ICMP ping probe
    let output = Command::new("ping")
        .args(["-c", "1", "-W", "1", tv_ip])
        .output();
    if let Ok(res) = output {
        if res.status.success() {
            return StatusResponse {
                status: "on".to_string(),
                method: "icmp".to_string(),
            };
        }
    }

    StatusResponse {
        status: "off".to_string(),
        method: "none".to_string(),
    }
}

pub async fn execute_soap(
    client: &reqwest::Client,
    tv_ip: &str,
    action: &str,
    body_xml: &str,
) -> Result<String, String> {
    let payload = format!(
        r#"<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <m:{} xmlns:m="urn:loewe.de:RemoteTV:Tablet">
      {}
    </m:{}>
  </s:Body>
</s:Envelope>"#,
        action, body_xml, action
    );

    let url = format!("http://{}:905/loewe_tablet_0001", tv_ip);
    let soap_action = format!(r#""urn:loewe.de:RemoteTV:Tablet#{}""#, action);

    let res = client
        .post(&url)
        .header(header::CONTENT_TYPE, r#"text/xml; charset="utf-8""#)
        .header("SOAPACTION", soap_action)
        .body(payload)
        .timeout(Duration::from_millis(2500))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if !res.status().is_success() {
        return Err(format!(
            "SOAP request failed with HTTP status {}: {}",
            res.status(),
            res.text().await.unwrap_or_default()
        ));
    }

    res.text().await.map_err(|e| e.to_string())
}

pub fn is_valid_key_response(text: &str) -> bool {
    text.contains("InjectRCKeyResponse")
        && text.contains("ClientId>")
        && !text.contains("INVALID")
        && text.contains("LRemoteClient")
}

pub fn is_valid_access_response(text: &str) -> bool {
    text.contains("RequestAccessResponse")
        && (text.contains("<m:AccessStatus>Accepted</m:AccessStatus>")
            || text.contains("AccessStatus>Accepted"))
        && text.contains("ClientId>")
        && text.contains("LRemoteClient")
}

pub fn escape_xml(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

pub async fn request_access(state: &AppState) -> Result<(String, String), String> {
    let safe_name = escape_xml(&state.device_name);
    let safe_uuid = escape_xml(&state.client_uuid);
    let body = format!(
        r#"<m:fcid>0</m:fcid>
      <m:DeviceType>Tablet</m:DeviceType>
      <m:DeviceName>{}</m:DeviceName>
      <m:DeviceUUID>{}</m:DeviceUUID>
      <m:RequesterName>{}</m:RequesterName>"#,
        safe_name, safe_uuid, safe_name
    );

    let xml = execute_soap(&state.http_client, &state.tv_ip, "RequestAccess", &body).await?;

    if !is_valid_access_response(&xml) {
        if xml.contains("Denied") {
            return Err("AccessStatus Denied: TV rejected remote pairing".to_string());
        }
        if xml.contains("Pending") {
            return Err(
                "AccessStatus Pending: Pairing confirmation required on TV screen".to_string(),
            );
        }
        return Err(format!("Invalid RequestAccess response from TV: {}", xml));
    }

    static CID_RE: std::sync::LazyLock<Regex> =
        std::sync::LazyLock::new(|| Regex::new(r"<m:ClientId>(.*?)</m:ClientId>").unwrap());
    static FCID_RE: std::sync::LazyLock<Regex> =
        std::sync::LazyLock::new(|| Regex::new(r"<m:fcid>(.*?)</m:fcid>").unwrap());

    let client_id = CID_RE
        .captures(&xml)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().trim().to_string())
        .filter(|s| !s.is_empty() && s.starts_with("LRemoteClient"))
        .ok_or_else(|| "Missing or invalid ClientId in RequestAccess response".to_string())?;

    let fcid = FCID_RE
        .captures(&xml)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().trim().to_string())
        .unwrap_or_else(|| DEFAULT_FCID.to_string());

    let effective_fcid = if fcid.is_empty() || fcid == "0" {
        DEFAULT_FCID.to_string()
    } else {
        fcid
    };

    let mut session = state.session.lock().await;
    session.client_id = Some(client_id.clone());
    session.fcid = effective_fcid.clone();

    Ok((client_id, effective_fcid))
}

pub async fn inject_key(state: &AppState, key_code: &str, alphabet: &str) -> Result<(), String> {
    // 1. Ensure authenticated session (safe initial handshake)
    let (mut client_id, mut fcid) = {
        let session = state.session.lock().await;
        (session.client_id.clone(), session.fcid.clone())
    };

    if client_id.is_none() {
        match request_access(state).await {
            Ok((cid, fid)) => {
                client_id = Some(cid);
                fcid = fid;
            }
            Err(e) => {
                return Err(format!("Initial handshake failed: {}", e));
            }
        }
    }

    let c_id = client_id.as_ref().unwrap();

    let body = format!(
        r#"<m:fcid>{}</m:fcid>
      <m:ClientId>{}</m:ClientId>
      <m:InputEventSequence>
        <m:RCKeyEvent alphabet="{}" mode="press" value="{}"/>
        <m:RCKeyEvent alphabet="{}" mode="release" value="{}"/>
      </m:InputEventSequence>"#,
        fcid, c_id, alphabet, key_code, alphabet, key_code
    );

    // 2. First attempt
    match execute_soap(&state.http_client, &state.tv_ip, "InjectRCKey", &body).await {
        Ok(resp) if is_valid_key_response(&resp) => Ok(()),
        first_res => {
            // Re-authenticate and retry exactly once
            warn!(
                "First key injection attempt failed ({:?}), re-authenticating...",
                first_res
            );
            let (new_cid, new_fcid) = match request_access(state).await {
                Ok(pair) => pair,
                Err(e) => {
                    return Err(format!("Session recovery handshake failed: {}", e));
                }
            };

            let retry_body = format!(
                r#"<m:fcid>{}</m:fcid>
      <m:ClientId>{}</m:ClientId>
      <m:InputEventSequence>
        <m:RCKeyEvent alphabet="{}" mode="press" value="{}"/>
        <m:RCKeyEvent alphabet="{}" mode="release" value="{}"/>
      </m:InputEventSequence>"#,
                new_fcid, new_cid, alphabet, key_code, alphabet, key_code
            );

            // 3. Retry attempt: CRUCIAL - MUST VERIFY RETRY RESPONSE TO PREVENT FALSE POSITIVE SUCCESS!
            match execute_soap(&state.http_client, &state.tv_ip, "InjectRCKey", &retry_body).await {
                Ok(retry_resp) if is_valid_key_response(&retry_resp) => Ok(()),
                Ok(retry_resp) => Err(format!(
                    "TV rejected key injection on retry: {}",
                    retry_resp
                )),
                Err(e) => Err(format!("Network error on key injection retry: {}", e)),
            }
        }
    }
}

// Handlers
async fn index_handler() -> impl IntoResponse {
    (
        [
            (header::CACHE_CONTROL, "no-cache, no-store, must-revalidate"),
            (header::PRAGMA, "no-cache"),
            (header::EXPIRES, "0"),
        ],
        Html(EMBEDDED_HTML),
    )
}

async fn status_handler(State(state): State<AppState>) -> impl IntoResponse {
    let tv_ip = state.tv_ip.clone();
    let status = tokio::task::spawn_blocking(move || probe_tv_status(&tv_ip))
        .await
        .unwrap_or(StatusResponse {
            status: "off".to_string(),
            method: "error".to_string(),
        });
    Json(status)
}

async fn wake_handler(State(state): State<AppState>) -> impl IntoResponse {
    let mac = state.mac_address.clone();
    let tv_ip = state.tv_ip.clone();
    let ok = tokio::task::spawn_blocking(move || wake_on_lan(&mac, &tv_ip))
        .await
        .unwrap_or(false);

    Json(ActionResponse {
        success: ok,
        action: "wake".to_string(),
        code: None,
        alphabet: None,
        error: None,
    })
}

async fn key_handler(
    State(state): State<AppState>,
    Query(params): Query<KeyParams>,
) -> impl IntoResponse {
    let (code_num, alphabet) = match params.validate() {
        Ok(v) => v,
        Err(err) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(ActionResponse {
                    success: false,
                    action: "key".to_string(),
                    code: Some(params.code),
                    alphabet: Some(params.alphabet),
                    error: Some(err.to_string()),
                }),
            );
        }
    };

    let code_str = code_num.to_string();
    match inject_key(&state, &code_str, alphabet).await {
        Ok(_) => (
            StatusCode::OK,
            Json(ActionResponse {
                success: true,
                action: "key".to_string(),
                code: Some(code_str),
                alphabet: Some(alphabet.to_string()),
                error: None,
            }),
        ),
        Err(err) => (
            StatusCode::BAD_GATEWAY,
            Json(ActionResponse {
                success: false,
                action: "key".to_string(),
                code: Some(code_str),
                alphabet: Some(alphabet.to_string()),
                error: Some(err),
            }),
        ),
    }
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    let args = CliArgs::parse();

    let hostname = std::env::var("HOSTNAME")
        .or_else(|_| std::env::var("HOST"))
        .unwrap_or_default();

    let device_name = match args.name {
        Some(name) => name,
        None if !hostname.is_empty() => format!("{}-{}", DEFAULT_DEVICE_NAME, hostname),
        None => DEFAULT_DEVICE_NAME.to_string(),
    };

    let client_uuid = match args.uuid {
        Some(uuid) => uuid,
        None if !hostname.is_empty() => {
            format!("{}-{}", DEFAULT_CLIENT_UUID, hostname.to_lowercase())
        }
        None => DEFAULT_CLIENT_UUID.to_string(),
    };

    let state = AppState {
        tv_ip: args.tv_ip.clone(),
        mac_address: args.mac.clone(),
        client_uuid,
        device_name,
        session: Arc::new(Mutex::new(SessionInfo {
            client_id: None,
            fcid: DEFAULT_FCID.to_string(),
        })),
        http_client: reqwest::Client::builder()
            .timeout(Duration::from_millis(2500))
            .build()
            .unwrap(),
    };

    let app = Router::new()
        .route("/", get(index_handler))
        .route("/index.html", get(index_handler))
        .route("/api/status", get(status_handler))
        .route("/api/wake", post(wake_handler))
        .route("/api/key", post(key_handler))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let bind_addr: SocketAddr = format!("{}:{}", args.bind, args.port)
        .parse()
        .expect("Invalid bind address");

    info!("=== Loewe Modern Web Remote (Rust Engine v1.0.0) ===");
    info!("Target TV IP: {} (MAC: {})", args.tv_ip, args.mac);
    info!("Listening on: http://{}", bind_addr);

    let listener = tokio::net::TcpListener::bind(bind_addr)
        .await
        .expect("Failed to bind TCP listener");
    axum::serve(listener, app).await.expect("Server error");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_valid_key_response() {
        let valid_xml = r#"<SOAP-ENV:Envelope><SOAP-ENV:Body>
            <m:InjectRCKeyResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">
                <m:fcid>2</m:fcid>
                <m:ClientId>LRemoteClient-0-1790240143</m:ClientId>
            </m:InjectRCKeyResponse>
        </SOAP-ENV:Body></SOAP-ENV:Envelope>"#;
        assert!(is_valid_key_response(valid_xml));

        // Critical test for '重试误报成功': TV returns INVALID ClientId
        let invalid_xml = r#"<SOAP-ENV:Envelope><SOAP-ENV:Body>
            <m:InjectRCKeyResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">
                <m:ClientId>INVALID</m:ClientId>
            </m:InjectRCKeyResponse>
        </SOAP-ENV:Body></SOAP-ENV:Envelope>"#;
        assert!(!is_valid_key_response(invalid_xml));

        let fault_xml = r#"<SOAP-ENV:Envelope><SOAP-ENV:Body>
            <SOAP-ENV:Fault><faultcode>SOAP-ENV:Server</faultcode></SOAP-ENV:Fault>
        </SOAP-ENV:Body></SOAP-ENV:Envelope>"#;
        assert!(!is_valid_key_response(fault_xml));
    }

    #[test]
    fn test_is_valid_access_response() {
        let accepted_xml = r#"<SOAP-ENV:Envelope><SOAP-ENV:Body>
            <m:RequestAccessResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">
                <m:fcid>0</m:fcid>
                <m:ClientId>LRemoteClient-0-998877</m:ClientId>
                <m:AccessStatus>Accepted</m:AccessStatus>
            </m:RequestAccessResponse>
        </SOAP-ENV:Body></SOAP-ENV:Envelope>"#;
        assert!(is_valid_access_response(accepted_xml));

        // Initial handshake anomaly: TV denies pairing request
        let denied_xml = r#"<SOAP-ENV:Envelope><SOAP-ENV:Body>
            <m:RequestAccessResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">
                <m:AccessStatus>Denied</m:AccessStatus>
            </m:RequestAccessResponse>
        </SOAP-ENV:Body></SOAP-ENV:Envelope>"#;
        assert!(!is_valid_access_response(denied_xml));

        // Initial handshake anomaly: TV requires on-screen PIN confirmation
        let pending_xml = r#"<SOAP-ENV:Envelope><SOAP-ENV:Body>
            <m:RequestAccessResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">
                <m:AccessStatus>Pending</m:AccessStatus>
            </m:RequestAccessResponse>
        </SOAP-ENV:Body></SOAP-ENV:Envelope>"#;
        assert!(!is_valid_access_response(pending_xml));
    }

    #[test]
    fn test_escape_xml() {
        assert_eq!(
            escape_xml("Living & Dining <Room> \"1\" 'TV'"),
            "Living &amp; Dining &lt;Room&gt; &quot;1&quot; &apos;TV&apos;"
        );
        assert_eq!(escape_xml("Normal-Name-123"), "Normal-Name-123");
    }
}
