use base64::Engine;
use clap::{Args, Parser, Subcommand};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::fs;
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};
use tungstenite::stream::MaybeTlsStream;
use tungstenite::{Message, WebSocket};

const CDP_PORT: u16 = 9222;
const PID_FILE: &str = "/tmp/fast_cdp_daemon.pid";

#[derive(Parser)]
#[command(name = "fast-cdp", about = "Ultra-fast native CDP client and Playwright verification engine")]
struct Cli {
    #[arg(short = 's', long, global = true, default_value = "default")]
    session: String,

    #[arg(long, global = true, default_value_t = 9222)]
    port: u16,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Daemon(DaemonArgs),
    Verify(VerifyArgs),
    Uat(UatArgs),
    Snap(SnapArgs),
    Nav(NavArgs),

    Open(OpenArgs),
    Attach(AttachArgs),
    Goto(GotoArgs),
    Snapshot(SnapshotArgs),
    Click(ClickArgs),
    Fill(FillArgs),
    Type(TypeArgs),
    Press(PressArgs),
    Eval(EvalArgs),
    Screenshot(ScreenshotArgs),
    Close(CloseArgs),
}

#[derive(Args)]
struct DaemonArgs {
    #[arg(value_parser = ["start", "stop", "status"])]
    action: String,
}

#[derive(Args)]
struct VerifyArgs {
    url: String,
    #[arg(long)]
    assert_selector: Option<String>,
    #[arg(long)]
    assert_text: Option<String>,
    #[arg(long = "eval")]
    eval_script: Option<String>,
    #[arg(long = "click")]
    click_selector: Option<String>,
    #[arg(long)]
    type_target: Option<String>,
    #[arg(long)]
    type_text: Option<String>,
    #[arg(long = "screenshot")]
    screenshot_path: Option<PathBuf>,
    #[arg(long, default_value_t = false)]
    no_block_media: bool,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct UatArgs {
    url: String,
    #[arg(long)]
    goal: String,
    #[arg(long)]
    expect_text: Option<String>,
    #[arg(long)]
    expect_url: Option<String>,
    /// Act on this exact candidate ref (as reported by --json) instead of
    /// matching the goal against element labels.
    #[arg(long = "ref")]
    target_ref: Option<String>,
    #[arg(long = "screenshot")]
    screenshot_path: Option<PathBuf>,
    #[arg(long, default_value_t = false)]
    no_block_media: bool,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct SnapArgs {
    url: String,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct NavArgs {
    url: String,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long = "screenshot")]
    screenshot_path: Option<PathBuf>,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct OpenArgs {
    url: Option<String>,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    no_block_media: bool,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct AttachArgs {
    #[arg(long)]
    cdp: Option<String>,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct GotoArgs {
    url: String,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct SnapshotArgs {
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct ClickArgs {
    target: String,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct FillArgs {
    target: String,
    text: String,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct TypeArgs {
    target: String,
    text: String,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct PressArgs {
    key: String,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct EvalArgs {
    expr: String,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct ScreenshotArgs {
    path: Option<PathBuf>,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct CloseArgs {
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Serialize)]
struct VerifyResult {
    ok: bool,
    url: String,
    title: String,
    duration_ms: f64,
    passed_checks: Vec<String>,
    errors: Vec<String>,
    eval_result: Option<Value>,
}

#[derive(Serialize)]
struct UatAction {
    action: String,
    ref_id: String,
    description: String,
    /// How the target was picked: `explicit_ref` or `keyword_match`.
    selection: String,
    /// Goal words found in the element's label.
    matched_on: Vec<String>,
    /// Share of the goal's words that matched, 0.0..1.0.
    match_score: f64,
}

#[derive(Serialize)]
struct UatResult {
    ok: bool,
    url: String,
    goal: String,
    duration_ms: f64,
    actions: Vec<UatAction>,
    verification: String,
    errors: Vec<String>,
}

#[derive(Deserialize)]
struct TargetInfo {
    id: String,
    #[serde(rename = "webSocketDebuggerUrl")]
    websocket_debugger_url: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
struct ActiveSession {
    target_id: String,
    ws_url: String,
    cdp_port: u16,
    url: String,
}

fn session_path(name: &str) -> PathBuf {
    PathBuf::from(format!("/tmp/fast_cdp_session_{name}.json"))
}

fn save_session(name: &str, session: &ActiveSession) -> Result<(), String> {
    let path = session_path(name);
    let json_str = serde_json::to_string_pretty(session).map_err(|e| e.to_string())?;
    fs::write(&path, json_str).map_err(|e| format!("Failed to write session file {}: {e}", path.display()))
}

fn load_session(name: &str) -> Result<ActiveSession, String> {
    let path = session_path(name);
    if !path.exists() {
        return Err(format!("No active session '{name}'. Run 'open <url>' or 'attach' first."));
    }
    let data = fs::read_to_string(&path).map_err(|e| format!("Failed to read session {}: {e}", path.display()))?;
    serde_json::from_str(&data).map_err(|e| format!("Corrupted session {}: {e}", path.display()))
}

fn remove_session(name: &str) {
    let _ = fs::remove_file(session_path(name));
}

fn resolve_target_selector(target: &str) -> String {
    let t = target.trim();
    if t.starts_with('e') && t.len() > 1 && t[1..].chars().all(|c| c.is_ascii_digit()) {
        format!("[data-fast-ref=\"{t}\"]")
    } else if let Some(stripped) = t.strip_prefix("ref=") {
        format!("[data-fast-ref=\"{stripped}\"]")
    } else {
        t.to_string()
    }
}

struct CdpClient {
    target_id: String,
    ws: WebSocket<MaybeTlsStream<TcpStream>>,
    msg_id: u64,
    cdp_port: u16,
    auto_close_on_drop: bool,
}

impl CdpClient {
    fn connect_ws(
        ws_url: &str,
        target_id: String,
        cdp_port: u16,
        auto_close: bool,
        timeout_ms: u64,
    ) -> Result<Self, String> {
        let (mut ws, _) = tungstenite::connect(ws_url)
            .map_err(|e| format!("WebSocket handshake to {ws_url} failed: {e}"))?;

        let stream = match ws.get_mut() {
            MaybeTlsStream::Plain(s) => s,
            _ => return Err("Expected plain TCP stream for localhost".into()),
        };
        stream
            .set_read_timeout(Some(Duration::from_millis(timeout_ms)))
            .map_err(|e| format!("Failed to set socket read timeout: {e}"))?;
        stream
            .set_write_timeout(Some(Duration::from_millis(timeout_ms)))
            .map_err(|e| format!("Failed to set socket write timeout: {e}"))?;

        let mut client = Self {
            target_id,
            ws,
            msg_id: 0,
            cdp_port,
            auto_close_on_drop: auto_close,
        };

        client.call("Page.enable", json!({}))?;
        client.call("Runtime.enable", json!({}))?;
        client.call("DOM.enable", json!({}))?;

        Ok(client)
    }

    fn new(block_media: bool, timeout_ms: u64) -> Result<Self, String> {
        let resp = ureq::put(&format!("http://127.0.0.1:{CDP_PORT}/json/new?about:blank"))
            .timeout(Duration::from_millis(timeout_ms))
            .call()
            .map_err(|e| format!("Failed to create CDP target: {e}"))?;

        let info: TargetInfo = resp
            .into_json()
            .map_err(|e| format!("Invalid target response JSON: {e}"))?;

        let ws_url = info
            .websocket_debugger_url
            .ok_or_else(|| "Target did not expose webSocketDebuggerUrl".to_string())?;

        let mut client = Self::connect_ws(&ws_url, info.id, CDP_PORT, true, timeout_ms)?;

        if block_media {
            let _ = client.call("Network.enable", json!({}));
            let _ = client.call(
                "Network.setBlockedURLs",
                json!({
                    "urls": [
                        "*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", "*.svg",
                        "*.woff*", "*.woff2", "*.ttf", "*analytics*", "*googletagmanager*"
                    ]
                }),
            );
        }

        Ok(client)
    }

    fn from_session(session: &ActiveSession, timeout_ms: u64) -> Result<Self, String> {
        let ws_url = if let Ok(resp) = ureq::get(&format!("http://127.0.0.1:{}/json/list", session.cdp_port))
            .timeout(Duration::from_millis(1000))
            .call()
        {
            if let Ok(targets) = resp.into_json::<Vec<Value>>() {
                targets
                    .into_iter()
                    .find(|t| t.get("id").and_then(Value::as_str) == Some(&session.target_id))
                    .and_then(|t| {
                        t.get("webSocketDebuggerUrl")
                            .and_then(Value::as_str)
                            .map(|s| s.to_string())
                    })
                    .unwrap_or_else(|| session.ws_url.clone())
            } else {
                session.ws_url.clone()
            }
        } else {
            session.ws_url.clone()
        };

        Self::connect_ws(&ws_url, session.target_id.clone(), session.cdp_port, false, timeout_ms)
    }

    fn call(&mut self, method: &str, params: Value) -> Result<Value, String> {
        self.msg_id += 1;
        let id = self.msg_id;
        let payload = json!({
            "id": id,
            "method": method,
            "params": params
        });

        self.ws
            .send(Message::Text(payload.to_string().into()))
            .map_err(|e| format!("Failed to send CDP command {method}: {e}"))?;

        loop {
            let msg = self
                .ws
                .read()
                .map_err(|e| format!("Error reading CDP response for {method}: {e}"))?;

            if let Message::Text(txt) = msg {
                let parsed: Value = match serde_json::from_str(&txt) {
                    Ok(v) => v,
                    Err(_) => continue,
                };

                if parsed.get("id").and_then(Value::as_u64) == Some(id) {
                    if let Some(err) = parsed.get("error") {
                        return Err(err
                            .get("message")
                            .and_then(Value::as_str)
                            .unwrap_or("Unknown CDP error")
                            .to_string());
                    }
                    return Ok(parsed.get("result").cloned().unwrap_or(Value::Null));
                }
            }
        }
    }

    fn evaluate(&mut self, expr: &str) -> Result<Value, String> {
        let res = self.call(
            "Runtime.evaluate",
            json!({
                "expression": expr,
                "returnByValue": true,
                "awaitPromise": true
            }),
        )?;

        if let Some(exception) = res.get("exceptionDetails") {
            let desc = exception
                .get("text")
                .and_then(Value::as_str)
                .or_else(|| {
                    exception
                        .get("exception")
                        .and_then(|e| e.get("description"))
                        .and_then(Value::as_str)
                })
                .unwrap_or("Runtime evaluation exception");
            return Err(desc.to_string());
        }

        Ok(res.get("result").cloned().unwrap_or(Value::Null))
    }

    fn navigate(&mut self, url: &str, timeout_ms: u64) -> Result<(), String> {
        let _ = self.call("Page.navigate", json!({ "url": url }))?;
        let start = Instant::now();
        let timeout = Duration::from_millis(timeout_ms);

        while start.elapsed() < timeout {
            if let Ok(state_val) = self.evaluate("document.readyState") {
                if let Some(s) = state_val.get("value").and_then(Value::as_str) {
                    if s == "interactive" || s == "complete" {
                        return Ok(());
                    }
                }
            }
            std::thread::sleep(Duration::from_millis(15));
        }

        Err(format!("Navigation to {url} timed out after {timeout_ms}ms"))
    }

    fn capture_screenshot(&mut self, path: &Path) -> Result<(), String> {
        let res = self.call("Page.captureScreenshot", json!({ "format": "png" }))?;
        let data_b64 = res
            .get("data")
            .and_then(Value::as_str)
            .ok_or_else(|| "Missing data in captureScreenshot response".to_string())?;

        let bytes = base64::engine::general_purpose::STANDARD
            .decode(data_b64)
            .map_err(|e| format!("Base64 decode error on screenshot: {e}"))?;

        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }

        fs::write(path, bytes).map_err(|e| format!("Failed to write screenshot file: {e}"))?;
        Ok(())
    }
}

impl Drop for CdpClient {
    fn drop(&mut self) {
        let _ = self.ws.close(None);
        if self.auto_close_on_drop {
            let _ = ureq::get(&format!(
                "http://127.0.0.1:{}/json/close/{}",
                self.cdp_port, self.target_id
            ))
            .timeout(Duration::from_millis(500))
            .call();
        }
    }
}

fn is_cdp_port_running(port: u16) -> bool {
    ureq::get(&format!("http://127.0.0.1:{port}/json/version"))
        .timeout(Duration::from_millis(400))
        .call()
        .map(|r| r.status() == 200)
        .unwrap_or(false)
}

fn find_chromium_binary() -> Option<PathBuf> {
    if let Ok(home) = std::env::var("HOME") {
        let cache = PathBuf::from(home).join(".cache/ms-playwright");
        if cache.exists() {
            let mut matches = Vec::new();
            if let Ok(entries) = glob_binary(&cache, "chrome-headless-shell") {
                matches.extend(entries);
            }
            if let Ok(entries) = glob_binary(&cache, "chrome") {
                matches.extend(entries);
            }
            for candidate in matches {
                if candidate.is_file() {
                    return Some(candidate);
                }
            }
        }
    }

    for name in &["chromium", "chromium-browser", "google-chrome"] {
        if let Ok(out) = Command::new("which").arg(name).output() {
            if out.status.success() {
                let path = String::from_utf8_lossy(&out.stdout).trim().to_string();
                if !path.is_empty() {
                    let pb = PathBuf::from(path);
                    if pb.is_file() {
                        return Some(pb);
                    }
                }
            }
        }
    }
    None
}

fn glob_binary(dir: &Path, name: &str) -> std::io::Result<Vec<PathBuf>> {
    let mut results = Vec::new();
    if dir.is_dir() {
        for entry in fs::read_dir(dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_dir() {
                results.extend(glob_binary(&path, name)?);
            } else if path.is_file() && path.file_name().and_then(|s| s.to_str()) == Some(name) {
                results.push(path);
            }
        }
    }
    Ok(results)
}

fn ensure_cdp_daemon_on_port(port: u16) -> Result<(), String> {
    if is_cdp_port_running(port) {
        return Ok(());
    }

    let binary = find_chromium_binary()
        .ok_or_else(|| "No headless chromium or chrome-headless-shell found".to_string())?;

    let child = Command::new("setsid")
        .arg(binary)
        .arg(format!("--remote-debugging-port={port}"))
        .arg("--no-sandbox")
        .arg("--disable-gpu")
        .arg("--disable-software-rasterizer")
        .arg("--disable-extensions")
        .arg("--disable-background-networking")
        .arg("--disable-sync")
        .arg("--no-first-run")
        .arg("--disable-default-apps")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Failed to spawn headless Chromium daemon: {e}"))?;

    let pid = child.id();
    let _ = fs::write(PID_FILE, pid.to_string());

    for _ in 0..40 {
        std::thread::sleep(Duration::from_millis(40));
        if is_cdp_port_running(port) {
            return Ok(());
        }
    }

    Err("Failed to start and warm CDP daemon within 1.6s".to_string())
}

fn stop_cdp_daemon() -> bool {
    let mut killed = false;
    if let Ok(content) = fs::read_to_string(PID_FILE) {
        if let Ok(pid) = content.trim().parse::<i32>() {
            let _ = Command::new("kill").arg("-15").arg(pid.to_string()).status();
            let _ = fs::remove_file(PID_FILE);
            killed = true;
        }
    }
    let _ = Command::new("pkill")
        .arg("-f")
        .arg("chrome-headless-shell.*--remote-debugging-port")
        .status();
    killed || !is_cdp_port_running(CDP_PORT)
}

fn run_open(
    session_name: &str,
    port: u16,
    args: OpenArgs,
) -> Result<(), Box<dyn std::error::Error>> {
    ensure_cdp_daemon_on_port(port).map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let target_url = args.url.as_deref().unwrap_or("about:blank");
    let full_url = if target_url != "about:blank"
        && !target_url.starts_with("http://")
        && !target_url.starts_with("https://")
        && !target_url.starts_with("file:")
        && !target_url.starts_with("data:")
    {
        format!("https://{target_url}")
    } else {
        target_url.to_string()
    };

    let create_endpoint = format!("http://127.0.0.1:{port}/json/new?about:blank");
    let resp = ureq::put(&create_endpoint)
        .timeout(Duration::from_millis(args.timeout))
        .call()
        .map_err(|e| format!("Failed to create CDP target at port {port}: {e}"))?;

    let info: TargetInfo = resp
        .into_json()
        .map_err(|e| format!("Invalid target response JSON: {e}"))?;

    let ws_url = info
        .websocket_debugger_url
        .ok_or_else(|| "Target did not expose webSocketDebuggerUrl".to_string())?;

    let mut client = CdpClient::connect_ws(&ws_url, info.id.clone(), port, false, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    if !args.no_block_media {
        let _ = client.call("Network.enable", json!({}));
        let _ = client.call(
            "Network.setBlockedURLs",
            json!({
                "urls": [
                    "*.woff*", "*.woff2", "*.ttf", "*analytics*", "*googletagmanager*"
                ]
            }),
        );
    }

    if full_url != "about:blank" {
        let _ = client.navigate(&full_url, args.timeout);
    }

    let title = client
        .evaluate("document.title")
        .ok()
        .and_then(|v| v.get("value").and_then(Value::as_str).map(|s| s.to_string()))
        .unwrap_or_default();

    let cur_url = client
        .evaluate("window.location.href")
        .ok()
        .and_then(|v| v.get("value").and_then(Value::as_str).map(|s| s.to_string()))
        .unwrap_or_else(|| full_url.clone());

    let session = ActiveSession {
        target_id: info.id.clone(),
        ws_url,
        cdp_port: port,
        url: cur_url.clone(),
    };

    save_session(session_name, &session)?;

    if args.json {
        let res = json!({
            "status": "opened",
            "session": session_name,
            "target_id": info.id,
            "url": cur_url,
            "title": title,
        });
        println!("{}", serde_json::to_string_pretty(&res)?);
    } else {
        println!("Opened browser session [{session_name}]: {cur_url} - {title}");
        println!("Ready for: snapshot, click, fill, type, press, eval, screenshot, close");
    }
    Ok(())
}

fn run_attach(
    session_name: &str,
    port: u16,
    args: AttachArgs,
) -> Result<(), Box<dyn std::error::Error>> {
    let cdp_base = args
        .cdp
        .unwrap_or_else(|| format!("http://127.0.0.1:{port}"));
    let list_endpoint = format!("{cdp_base}/json/list");

    let resp = ureq::get(&list_endpoint)
        .timeout(Duration::from_millis(2000))
        .call()
        .map_err(|e| format!("Failed to reach CDP list at {list_endpoint}: {e}"))?;

    let targets: Vec<Value> = resp
        .into_json()
        .map_err(|e| format!("Invalid target list JSON: {e}"))?;

    let page_target = targets
        .into_iter()
        .find(|t| t.get("type").and_then(Value::as_str) == Some("page"))
        .ok_or_else(|| "No page target found on CDP endpoint".to_string())?;

    let target_id = page_target
        .get("id")
        .and_then(Value::as_str)
        .ok_or_else(|| "Target missing ID".to_string())?
        .to_string();

    let ws_url = page_target
        .get("webSocketDebuggerUrl")
        .and_then(Value::as_str)
        .ok_or_else(|| "Target missing webSocketDebuggerUrl".to_string())?
        .to_string();

    let cur_url = page_target
        .get("url")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();

    let session = ActiveSession {
        target_id: target_id.clone(),
        ws_url,
        cdp_port: port,
        url: cur_url.clone(),
    };

    save_session(session_name, &session)?;

    if args.json {
        let res = json!({
            "status": "attached",
            "session": session_name,
            "target_id": target_id,
            "url": cur_url
        });
        println!("{}", serde_json::to_string_pretty(&res)?);
    } else {
        println!("Attached to session [{session_name}]: {cur_url} (target: {target_id})");
    }
    Ok(())
}

fn run_goto(session_name: &str, args: GotoArgs) -> Result<(), Box<dyn std::error::Error>> {
    let session = load_session(session_name)?;
    let mut client = CdpClient::from_session(&session, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let target_url = if !args.url.starts_with("http://")
        && !args.url.starts_with("https://")
        && !args.url.starts_with("file:")
        && !args.url.starts_with("data:")
    {
        format!("https://{}", args.url)
    } else {
        args.url.clone()
    };

    client
        .navigate(&target_url, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let title = client
        .evaluate("document.title")
        .ok()
        .and_then(|v| v.get("value").and_then(Value::as_str).map(|s| s.to_string()))
        .unwrap_or_default();

    let cur_url = client
        .evaluate("window.location.href")
        .ok()
        .and_then(|v| v.get("value").and_then(Value::as_str).map(|s| s.to_string()))
        .unwrap_or_else(|| target_url.clone());

    let mut updated_session = session;
    updated_session.url = cur_url.clone();
    save_session(session_name, &updated_session)?;

    if args.json {
        let res = json!({
            "status": "navigated",
            "session": session_name,
            "url": cur_url,
            "title": title
        });
        println!("{}", serde_json::to_string_pretty(&res)?);
    } else {
        println!("Navigated [{session_name}]: {cur_url} - {title}");
    }
    Ok(())
}

fn run_snapshot(
    session_name: &str,
    args: SnapshotArgs,
) -> Result<(), Box<dyn std::error::Error>> {
    let session = load_session(session_name)?;
    let mut client = CdpClient::from_session(&session, 5000)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let snap_script = r#"
    (() => {
        document.querySelectorAll('[data-fast-ref]').forEach(el => el.removeAttribute('data-fast-ref'));
        let counter = 0;
        const elements = [];
        const lines = [];

        const isVisible = (el) => {
            if (!el || el.nodeType !== Node.ELEMENT_NODE) return false;
            if (el.tagName === 'BODY' || el.tagName === 'HTML') return true;
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
            if (el.offsetWidth === 0 && el.offsetHeight === 0 && style.position !== 'fixed' && style.position !== 'absolute') return false;
            return true;
        };

        const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();

        const query = 'a[href], button, input, textarea, select, [role="button"], [role="link"], [role="textbox"], [role="checkbox"], [role="tab"], [role="menuitem"], [tabindex="0"], h1, h2, h3, h4, h5, h6';
        const all = document.querySelectorAll(query);

        for (const el of all) {
            if (!isVisible(el)) continue;
            const tag = el.tagName.toLowerCase();
            let role = el.getAttribute('role') || tag;
            let text = clean(el.innerText);
            const ariaLabel = clean(el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || '');

            if (tag.startsWith('h') && tag.length === 2 && !isNaN(tag[1])) {
                lines.push(`- heading "${text || ariaLabel}" [level=${tag[1]}]`);
                continue;
            }

            counter += 1;
            const refId = 'e' + counter;
            el.setAttribute('data-fast-ref', refId);

            let desc = ariaLabel || text;
            if (tag === 'input') {
                const inputType = el.getAttribute('type') || 'text';
                if (inputType === 'checkbox' || inputType === 'radio') {
                    role = inputType;
                    desc = `${desc || el.name || ''} ${el.checked ? '[checked]' : '[unchecked]'}`.trim();
                } else if (inputType === 'submit' || inputType === 'button') {
                    role = 'button';
                    desc = el.value || desc || 'Submit';
                } else {
                    role = 'textbox';
                    const val = el.value ? ` (value: "${clean(el.value)}")` : '';
                    desc = `${desc || el.name || 'text'}${val}`;
                }
            } else if (tag === 'select') {
                role = 'combobox';
                const selected = el.selectedOptions[0] ? clean(el.selectedOptions[0].text) : '';
                desc = `${desc} (selected: "${selected}")`.trim();
            } else if (tag === 'a') {
                role = 'link';
                if (!desc) desc = el.getAttribute('href') || 'link';
            }

            elements.push({
                ref: refId,
                role: role,
                text: desc,
                tag: tag,
                selector: `[data-fast-ref="${refId}"]`
            });

            lines.push(`- ${role} "${desc}" [ref=${refId}]`);
        }

        return {
            url: window.location.href,
            title: document.title,
            text: lines.join('\n'),
            elements: elements
        };
    })()
    "#;

    let res_val = client.evaluate(snap_script)?;
    let res_obj = res_val
        .get("value")
        .ok_or_else(|| "Missing snapshot evaluation value".to_string())?;

    if args.json {
        println!("{}", serde_json::to_string_pretty(res_obj)?);
    } else {
        let title = res_obj.get("title").and_then(Value::as_str).unwrap_or("");
        let url = res_obj.get("url").and_then(Value::as_str).unwrap_or("");
        let text = res_obj.get("text").and_then(Value::as_str).unwrap_or("");
        println!("Page: {title} ({url})\n---\n{text}");
    }
    Ok(())
}

fn run_click(session_name: &str, args: ClickArgs) -> Result<(), Box<dyn std::error::Error>> {
    let session = load_session(session_name)?;
    let mut client = CdpClient::from_session(&session, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let sel = resolve_target_selector(&args.target);
    let script = format!(
        r#"(() => {{
            const el = document.querySelector({sel_json});
            if (!el) throw new Error("Element not found: " + {sel_json});
            el.scrollIntoView({{ behavior: "instant", block: "center", inline: "center" }});
            el.focus();
            el.click();
            return {{
                ok: true,
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || el.value || el.getAttribute("aria-label") || "").trim()
            }};
        }})()"#,
        sel_json = json!(sel)
    );

    let res_val = client.evaluate(&script)?;
    let res = res_val.get("value").cloned().unwrap_or(Value::Null);

    if args.json {
        println!("{}", serde_json::to_string_pretty(&res)?);
    } else {
        println!("Clicked: {} ({sel})", args.target);
    }
    Ok(())
}

fn run_fill(session_name: &str, args: FillArgs) -> Result<(), Box<dyn std::error::Error>> {
    let session = load_session(session_name)?;
    let mut client = CdpClient::from_session(&session, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let sel = resolve_target_selector(&args.target);
    let script = format!(
        r#"(() => {{
            const el = document.querySelector({sel_json});
            if (!el) throw new Error("Element not found: " + {sel_json});
            el.scrollIntoView({{ behavior: "instant", block: "center", inline: "center" }});
            el.focus();
            el.value = {text_json};
            el.dispatchEvent(new Event("input", {{ bubbles: true }}));
            el.dispatchEvent(new Event("change", {{ bubbles: true }}));
            return {{
                ok: true,
                tag: el.tagName.toLowerCase(),
                value: el.value
            }};
        }})()"#,
        sel_json = json!(sel),
        text_json = json!(args.text)
    );

    let res_val = client.evaluate(&script)?;
    let res = res_val.get("value").cloned().unwrap_or(Value::Null);

    if args.json {
        println!("{}", serde_json::to_string_pretty(&res)?);
    } else {
        println!("Filled: {} with \"{}\"", args.target, args.text);
    }
    Ok(())
}

fn run_type(session_name: &str, args: TypeArgs) -> Result<(), Box<dyn std::error::Error>> {
    run_fill(
        session_name,
        FillArgs {
            target: args.target,
            text: args.text,
            timeout: args.timeout,
            json: args.json,
        },
    )
}

fn run_press(session_name: &str, args: PressArgs) -> Result<(), Box<dyn std::error::Error>> {
    let session = load_session(session_name)?;
    let mut client = CdpClient::from_session(&session, 5000)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let (key_code, win_code) = match args.key.to_lowercase().as_str() {
        "enter" => ("Enter", 13),
        "tab" => ("Tab", 9),
        "escape" | "esc" => ("Escape", 27),
        "backspace" => ("Backspace", 8),
        "arrowdown" | "down" => ("ArrowDown", 40),
        "arrowup" | "up" => ("ArrowUp", 38),
        "arrowleft" | "left" => ("ArrowLeft", 37),
        "arrowright" | "right" => ("ArrowRight", 39),
        "space" => ("Space", 32),
        _ => (args.key.as_str(), 0),
    };

    let _ = client.call(
        "Input.dispatchKeyEvent",
        json!({
            "type": "rawKeyDown",
            "key": key_code,
            "code": key_code,
            "windowsVirtualKeyCode": win_code,
            "nativeVirtualKeyCode": win_code,
        }),
    )?;

    let _ = client.call(
        "Input.dispatchKeyEvent",
        json!({
            "type": "keyUp",
            "key": key_code,
            "code": key_code,
            "windowsVirtualKeyCode": win_code,
            "nativeVirtualKeyCode": win_code,
        }),
    )?;

    if args.json {
        println!("{}", json!({"status": "pressed", "key": args.key}));
    } else {
        println!("Pressed: {}", args.key);
    }
    Ok(())
}

fn run_eval(session_name: &str, args: EvalArgs) -> Result<(), Box<dyn std::error::Error>> {
    let session = load_session(session_name)?;
    let mut client = CdpClient::from_session(&session, 5000)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let res_val = client.evaluate(&args.expr)?;
    let res = res_val.get("value").cloned().unwrap_or(Value::Null);

    if args.json {
        println!("{}", serde_json::to_string_pretty(&res)?);
    } else if let Some(s) = res.as_str() {
        println!("{s}");
    } else {
        println!("{res}");
    }
    Ok(())
}

fn run_screenshot(
    session_name: &str,
    args: ScreenshotArgs,
) -> Result<(), Box<dyn std::error::Error>> {
    let session = load_session(session_name)?;
    let mut client = CdpClient::from_session(&session, 5000)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let path = args
        .path
        .unwrap_or_else(|| PathBuf::from(format!("/tmp/fast_cdp_{session_name}.png")));
    client
        .capture_screenshot(&path)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    if args.json {
        println!(
            "{}",
            json!({"status": "saved", "path": path.display().to_string()})
        );
    } else {
        println!("Screenshot saved: {}", path.display());
    }
    Ok(())
}

fn run_close(session_name: &str, args: CloseArgs) -> Result<(), Box<dyn std::error::Error>> {
    if let Ok(session) = load_session(session_name) {
        let _ = ureq::get(&format!(
            "http://127.0.0.1:{}/json/close/{}",
            session.cdp_port, session.target_id
        ))
        .timeout(Duration::from_millis(500))
        .call();
        remove_session(session_name);
    }

    if args.json {
        println!("{}", json!({"status": "closed", "session": session_name}));
    } else {
        println!("Closed session [{session_name}]");
    }
    Ok(())
}

fn run_verify(args: VerifyArgs) -> Result<(), Box<dyn std::error::Error>> {
    let start = Instant::now();
    ensure_cdp_daemon_on_port(CDP_PORT)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let mut client = CdpClient::new(!args.no_block_media, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let mut passed_checks = Vec::new();
    let mut errors = Vec::new();
    let mut eval_result = None;
    let mut page_title = String::new();

    let target_url = if !args.url.starts_with("http://")
        && !args.url.starts_with("https://")
        && !args.url.starts_with("data:")
        && !args.url.starts_with("file:")
    {
        format!("https://{}", args.url)
    } else {
        args.url.clone()
    };

    if let Err(e) = client.navigate(&target_url, args.timeout) {
        errors.push(e);
    } else {
        if let Ok(title_val) = client.evaluate("document.title") {
            if let Some(t) = title_val.get("value").and_then(Value::as_str) {
                page_title = t.to_string();
            }
        }

        if let Some(ref sel) = args.click_selector {
            let script = format!(
                r#"(() => {{
                    const el = document.querySelector({});
                    if (!el) throw new Error("Click selector not found: " + {});
                    el.scrollIntoView({{block: "center", inline: "center"}});
                    el.click();
                    return true;
                }})()"#,
                json!(sel),
                json!(sel)
            );
            match client.evaluate(&script) {
                Ok(_) => passed_checks.push(format!("click:{sel}")),
                Err(e) => errors.push(e),
            }
        }

        if let (Some(target), Some(text)) = (&args.type_target, &args.type_text) {
            let script = format!(
                r#"(() => {{
                    const el = document.querySelector({});
                    if (!el) throw new Error("Type target not found: " + {});
                    el.focus();
                    el.value = {};
                    el.dispatchEvent(new Event("input", {{ bubbles: true }}));
                    el.dispatchEvent(new Event("change", {{ bubbles: true }}));
                    return true;
                }})()"#,
                json!(target),
                json!(target),
                json!(text)
            );
            match client.evaluate(&script) {
                Ok(_) => passed_checks.push(format!("type:{target}")),
                Err(e) => errors.push(e),
            }
        }

        if let Some(ref sel) = args.assert_selector {
            let script = format!(
                r#"(() => {{
                    return document.querySelector({}) !== null;
                }})()"#,
                json!(sel)
            );
            match client.evaluate(&script) {
                Ok(val) if val.get("value").and_then(Value::as_bool) == Some(true) => {
                    passed_checks.push(format!("selector:{sel}"));
                }
                Ok(_) => errors.push(format!("Selector '{sel}' did not exist in DOM")),
                Err(e) => errors.push(e),
            }
        }

        if let Some(ref text) = args.assert_text {
            let script = format!(
                r#"(() => {{
                    return (document.body ? document.body.innerText : "").includes({});
                }})()"#,
                json!(text)
            );
            match client.evaluate(&script) {
                Ok(val) if val.get("value").and_then(Value::as_bool) == Some(true) => {
                    passed_checks.push(format!("text:{text}"));
                }
                Ok(_) => errors.push(format!("Text '{text}' not found in body text")),
                Err(e) => errors.push(e),
            }
        }

        if let Some(ref expr) = args.eval_script {
            match client.evaluate(expr) {
                Ok(val) => {
                    eval_result = val.get("value").cloned();
                    passed_checks.push(format!("eval:{expr}"));
                }
                Err(e) => errors.push(e),
            }
        }

        if let Some(ref path) = args.screenshot_path {
            match client.capture_screenshot(path) {
                Ok(_) => passed_checks.push(format!("screenshot:{}", path.display())),
                Err(e) => errors.push(e),
            }
        }
    }

    let duration_ms = (start.elapsed().as_secs_f64() * 1000.0 * 100.0).round() / 100.0;
    let res = VerifyResult {
        ok: errors.is_empty(),
        url: target_url,
        title: page_title,
        duration_ms,
        passed_checks,
        errors,
        eval_result,
    };

    if args.json {
        println!("{}", serde_json::to_string_pretty(&res)?);
    } else {
        println!(
            "[{}] {} ({:.1}ms)",
            if res.ok { "PASS" } else { "FAIL" },
            res.url,
            res.duration_ms
        );
        for check in &res.passed_checks {
            println!("  ✓ {check}");
        }
        for err in &res.errors {
            eprintln!("  ✗ {err}");
        }
    }

    if !res.ok {
        std::process::exit(1);
    }
    Ok(())
}

fn run_snap(args: SnapArgs) -> Result<(), Box<dyn std::error::Error>> {
    ensure_cdp_daemon_on_port(CDP_PORT)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
    let mut client = CdpClient::new(true, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let target_url = if !args.url.starts_with("http://")
        && !args.url.starts_with("https://")
        && !args.url.starts_with("data:")
    {
        format!("https://{}", args.url)
    } else {
        args.url.clone()
    };

    client
        .navigate(&target_url, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let text_val = client.evaluate("document.body ? document.body.innerText : ''")?;
    let text = text_val
        .get("value")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();

    let title_val = client.evaluate("document.title")?;
    let title = title_val
        .get("value")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();

    if args.json {
        let out = json!({
            "url": target_url,
            "title": title,
            "text": text,
        });
        println!("{}", serde_json::to_string_pretty(&out)?);
    } else {
        println!("Title: {title}\nURL: {target_url}\n---\n{text}");
    }
    Ok(())
}

fn run_nav(args: NavArgs) -> Result<(), Box<dyn std::error::Error>> {
    ensure_cdp_daemon_on_port(CDP_PORT)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
    let mut client = CdpClient::new(false, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let target_url = if !args.url.starts_with("http://")
        && !args.url.starts_with("https://")
        && !args.url.starts_with("data:")
    {
        format!("https://{}", args.url)
    } else {
        args.url.clone()
    };

    client
        .navigate(&target_url, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let title_val = client.evaluate("document.title")?;
    let title = title_val
        .get("value")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();

    if let Some(ref path) = args.screenshot_path {
        client
            .capture_screenshot(path)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
    }

    if args.json {
        let out = json!({
            "url": target_url,
            "title": title,
            "screenshot": args.screenshot_path.map(|p| p.display().to_string())
        });
        println!("{}", serde_json::to_string_pretty(&out)?);
    } else {
        println!("Navigated to {target_url} - {title}");
    }
    Ok(())
}

fn run_uat(args: UatArgs) -> Result<(), Box<dyn std::error::Error>> {
    let start = Instant::now();
    ensure_cdp_daemon_on_port(CDP_PORT)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
    let mut client = CdpClient::new(!args.no_block_media, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let target_url = if !args.url.starts_with("http://")
        && !args.url.starts_with("https://")
        && !args.url.starts_with("data:")
    {
        format!("https://{}", args.url)
    } else {
        args.url.clone()
    };

    client
        .navigate(&target_url, args.timeout)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let extract_script = r#"
    (() => {
        const elements = [];
        const candidates = document.querySelectorAll('button, a, input, select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])');
        let idx = 0;
        for (const el of candidates) {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
                idx++;
                const tag = el.tagName.toLowerCase();
                const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.id || '').trim().replace(/\s+/g, ' ').slice(0, 80);
                const role = el.getAttribute('role') || tag;
                const ref = `uat-${idx}`;
                el.setAttribute('data-uat-ref', ref);
                elements.push({
                    ref: ref,
                    description: `${role} '${text}'`
                });
            }
        }
        return elements;
    })()
    "#;

    let candidates_val = client.evaluate(extract_script)?;
    let candidates_arr = candidates_val
        .get("value")
        .and_then(Value::as_array)
        .ok_or_else(|| "Failed to extract candidate elements".to_string())
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    if candidates_arr.is_empty() {
        return Err(format!("No interactive elements found on page: {target_url}").into());
    }

    // Ordered, not a HashMap: ties must resolve in DOM order to be
    // reproducible across runs.
    let mut candidates: Vec<(String, String)> = Vec::new();
    for c in candidates_arr.iter().take(20) {
        if let (Some(r), Some(d)) = (
            c.get("ref").and_then(Value::as_str),
            c.get("description").and_then(Value::as_str),
        ) {
            candidates.push((r.to_string(), d.to_string()));
        }
    }

    let keywords = goal_keywords(&args.goal);

    let (selected_ref, matched_on, match_score, how) = match args.target_ref.as_deref() {
        Some(wanted) => {
            if !candidates.iter().any(|(r, _)| r == wanted) {
                return Err(format!(
                    "--ref '{wanted}' is not on the page. Candidates:\n{}",
                    list_candidates(&candidates)
                )
                .into());
            }
            (wanted.to_string(), Vec::new(), 1.0, "explicit_ref")
        }
        None => match select_target(&keywords, &candidates) {
            Some((ref_id, matched, score)) => (ref_id, matched, score, "keyword_match"),
            None => {
                return Err(format!(
                    "No candidate matched the goal '{}'. Pass --ref to pick one of:\n{}",
                    args.goal,
                    list_candidates(&candidates)
                )
                .into());
            }
        },
    };

    let selected_desc = candidates
        .iter()
        .find(|(r, _)| r == &selected_ref)
        .map(|(_, d)| d.clone())
        .unwrap_or_else(|| "Unknown".to_string());

    let mut actions = Vec::new();
    actions.push(UatAction {
        action: "click".to_string(),
        ref_id: selected_ref.clone(),
        description: selected_desc,
        selection: how.to_string(),
        matched_on,
        match_score,
    });

    let click_script = format!(
        r#"(() => {{
            const el = document.querySelector('[data-uat-ref="{}"]');
            if (!el) throw new Error("Element not found: " + "{}");
            el.click();
            return true;
        }})()"#,
        selected_ref, selected_ref
    );
    client
        .evaluate(&click_script)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    std::thread::sleep(Duration::from_millis(100));

    let mut errors = Vec::new();

    if let Some(ref expect_text) = args.expect_text {
        let body_val = client.evaluate("document.body ? document.body.innerText : ''")?;
        let body_text = body_val.get("value").and_then(Value::as_str).unwrap_or("");
        if !body_text.contains(expect_text) {
            errors.push(format!(
                "Expected UAT text '{expect_text}' not found after action"
            ));
        }
    }

    if let Some(ref expect_url) = args.expect_url {
        let url_val = client.evaluate("window.location.href")?;
        let current_url = url_val.get("value").and_then(Value::as_str).unwrap_or("");
        if !current_url.contains(expect_url) {
            errors.push(format!(
                "Expected UAT URL to contain '{expect_url}', got '{current_url}'"
            ));
        }
    }

    if let Some(ref path) = args.screenshot_path {
        let _ = client.capture_screenshot(path);
    }

    // Without an assertion there is nothing to verify, and a model's opinion
    // of "that looks about right" is exactly the unverifiable claim UAT exists
    // to remove. Say so plainly instead.
    let asserted = args.expect_text.is_some() || args.expect_url.is_some();
    let verification = if !errors.is_empty() {
        "failed".to_string()
    } else if asserted {
        "verified_by_assertions".to_string()
    } else {
        "action_executed".to_string()
    };

    let duration_ms = (start.elapsed().as_secs_f64() * 1000.0 * 100.0).round() / 100.0;
    let res = UatResult {
        ok: errors.is_empty(),
        url: target_url,
        goal: args.goal,
        duration_ms,
        actions,
        verification,
        errors,
    };

    if args.json {
        println!("{}", serde_json::to_string_pretty(&res)?);
    } else {
        println!(
            "[{}] UAT: {} ({:.1}ms)",
            if res.ok { "PASS" } else { "FAIL" },
            res.goal,
            res.duration_ms
        );
        for a in &res.actions {
            println!(
                "  Action: click {} ({}) [{} score: {:.2}]",
                a.ref_id, a.description, a.selection, a.match_score
            );
        }
        for err in &res.errors {
            eprintln!("  ✗ {err}");
        }
    }

    if !res.ok {
        std::process::exit(1);
    }
    Ok(())
}

/// Split a goal into comparable words: lowercased, alphanumeric, >= 3 chars.
fn goal_keywords(goal: &str) -> Vec<String> {
    goal.split(|c: char| !c.is_alphanumeric())
        .filter(|w| w.len() >= 3)
        .map(|w| w.to_lowercase())
        .collect()
}

fn list_candidates(candidates: &[(String, String)]) -> String {
    candidates
        .iter()
        .map(|(r, d)| format!("  {r}: {d}"))
        .collect::<Vec<_>>()
        .join("\n")
}

/// Pick the candidate whose label covers the most of the goal's words.
///
/// `uat` used to hand this list to a decision model. The list is already
/// resolved from the DOM by the extraction script above, so that was a model
/// round trip to redo a choice the caller had already made -- and it made a
/// deterministic browser test depend on a multi-gigabyte server being up.
/// Scoring labels locally is reproducible, needs no VRAM, and reports the
/// words it matched so a wrong pick is debuggable.
///
/// Ties break toward the earlier element in DOM order. Returns `None` when
/// nothing matches, so the caller can ask for an explicit `--ref`.
fn select_target(
    keywords: &[String],
    candidates: &[(String, String)],
) -> Option<(String, Vec<String>, f64)> {
    if keywords.is_empty() {
        return None;
    }

    let mut best: Option<(usize, String, Vec<String>, usize)> = None;
    for (idx, (ref_id, description)) in candidates.iter().enumerate() {
        let haystack = description.to_lowercase();
        let matched: Vec<String> = keywords
            .iter()
            .filter(|k| haystack.contains(k.as_str()))
            .cloned()
            .collect();
        if matched.is_empty() {
            continue;
        }
        // Strictly greater keeps the earlier candidate on a tie.
        if best.as_ref().is_none_or(|(count, _, _, _)| matched.len() > *count) {
            best = Some((matched.len(), ref_id.clone(), matched, idx));
        }
    }

    best.map(|(count, ref_id, matched, _idx)| {
        let score = (count as f64 / keywords.len() as f64 * 1000.0).round() / 1000.0;
        (ref_id, matched, score)
    })
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let session = cli.session.as_str();
    let port = cli.port;

    match cli.command {
        Commands::Daemon(d) => match d.action.as_str() {
            "start" => {
                ensure_cdp_daemon_on_port(port)?;
                println!(
                    "{}",
                    json!({"status": "running", "cdp_url": format!("http://127.0.0.1:{port}")})
                );
            }
            "stop" => {
                let stopped = stop_cdp_daemon();
                println!(
                    "{}",
                    json!({"status": if stopped { "stopped" } else { "not_running" }})
                );
            }
            "status" => {
                let running = is_cdp_port_running(port);
                println!(
                    "{}",
                    json!({
                        "status": if running { "running" } else { "stopped" },
                        "cdp_url": format!("http://127.0.0.1:{port}")
                    })
                );
            }
            _ => unreachable!(),
        },
        Commands::Verify(v) => run_verify(v)?,
        Commands::Uat(u) => run_uat(u)?,
        Commands::Snap(s) => run_snap(s)?,
        Commands::Nav(n) => run_nav(n)?,

        Commands::Open(o) => run_open(session, port, o)?,
        Commands::Attach(a) => run_attach(session, port, a)?,
        Commands::Goto(g) => run_goto(session, g)?,
        Commands::Snapshot(s) => run_snapshot(session, s)?,
        Commands::Click(c) => run_click(session, c)?,
        Commands::Fill(f) => run_fill(session, f)?,
        Commands::Type(t) => run_type(session, t)?,
        Commands::Press(p) => run_press(session, p)?,
        Commands::Eval(e) => run_eval(session, e)?,
        Commands::Screenshot(s) => run_screenshot(session, s)?,
        Commands::Close(c) => run_close(session, c)?,
    }
    Ok(())
}
