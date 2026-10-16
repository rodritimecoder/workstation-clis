use base64::Engine;
use clap::{Args, Parser, Subcommand};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::HashMap;
use std::fs;
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};
use tungstenite::stream::MaybeTlsStream;
use tungstenite::{Message, WebSocket};

const CDP_PORT: u16 = 9222;
const CDP_URL: &str = "http://127.0.0.1:9222";
const PID_FILE: &str = "/tmp/fast_cdp_daemon.pid";

#[derive(Parser)]
#[command(name = "fast-cdp", about = "Ultra-fast native CDP client and verification engine")]
struct Cli {
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
    #[arg(long, default_value = "jpt", value_parser = ["jpt", "imajev"])]
    model: String,
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
    probability: f64,
    confidence: f64,
    model: String,
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

struct CdpClient {
    target_id: String,
    ws: WebSocket<MaybeTlsStream<TcpStream>>,
    msg_id: u64,
}

impl CdpClient {
    fn new(block_media: bool, timeout_ms: u64) -> Result<Self, String> {
        let resp = ureq::put(&format!("{CDP_URL}/json/new?about:blank"))
            .timeout(Duration::from_millis(timeout_ms))
            .call()
            .map_err(|e| format!("Failed to create CDP target: {e}"))?;

        let info: TargetInfo = resp
            .into_json()
            .map_err(|e| format!("Invalid target response JSON: {e}"))?;

        let ws_url = info
            .websocket_debugger_url
            .ok_or_else(|| "Target did not expose webSocketDebuggerUrl".to_string())?;

        let (mut ws, _) = tungstenite::connect(&ws_url)
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
            target_id: info.id,
            ws,
            msg_id: 0,
        };

        client.call("Page.enable", json!({}))?;
        client.call("Runtime.enable", json!({}))?;
        client.call("DOM.enable", json!({}))?;

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
        let _ = ureq::get(&format!("{CDP_URL}/json/close/{}", self.target_id))
            .timeout(Duration::from_millis(500))
            .call();
    }
}

fn is_cdp_running() -> bool {
    ureq::get(&format!("{CDP_URL}/json/version"))
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

fn ensure_cdp_daemon() -> Result<(), String> {
    if is_cdp_running() {
        return Ok(());
    }

    let binary = find_chromium_binary()
        .ok_or_else(|| "No headless chromium or chrome-headless-shell found".to_string())?;

    let child = Command::new(binary)
        .arg(format!("--remote-debugging-port={CDP_PORT}"))
        .arg("--no-sandbox")
        .arg("--disable-gpu")
        .arg("--disable-software-rasterizer")
        .arg("--disable-extensions")
        .arg("--disable-background-networking")
        .arg("--disable-sync")
        .arg("--no-first-run")
        .arg("--disable-default-apps")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Failed to spawn headless Chromium daemon: {e}"))?;

    let pid = child.id();
    let _ = fs::write(PID_FILE, pid.to_string());

    for _ in 0..40 {
        std::thread::sleep(Duration::from_millis(40));
        if is_cdp_running() {
            return Ok(());
        }
    }

    Err("Failed to start and warm CDP daemon within 1.6s".to_string())
}

fn stop_cdp_daemon() -> bool {
    if let Ok(content) = fs::read_to_string(PID_FILE) {
        if let Ok(pid) = content.trim().parse::<i32>() {
            let _ = Command::new("kill").arg("-15").arg(pid.to_string()).status();
            let _ = fs::remove_file(PID_FILE);
            return true;
        }
    }
    false
}

fn run_verify(args: VerifyArgs) -> Result<(), Box<dyn std::error::Error>> {
    let start = Instant::now();
    ensure_cdp_daemon().map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

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
    ensure_cdp_daemon().map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
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
    ensure_cdp_daemon().map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
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
    ensure_cdp_daemon().map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
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

    let mut options = HashMap::new();
    for c in candidates_arr.iter().take(20) {
        if let (Some(r), Some(d)) = (
            c.get("ref").and_then(Value::as_str),
            c.get("description").and_then(Value::as_str),
        ) {
            options.insert(r.to_string(), d.to_string());
        }
    }

    let title_val = client.evaluate("document.title")?;
    let page_title = title_val
        .get("value")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();

    let options_prompt = options
        .iter()
        .map(|(r, d)| format!("- {r}: {d}"))
        .collect::<Vec<_>>()
        .join("\n");
    let state = format!(
        "Page Title: {page_title}\nURL: {target_url}\nGoal: {}\nInteractive Elements:\n{options_prompt}",
        args.goal
    );
    let question = format!(
        "Which interactive element should be clicked or triggered to achieve: '{}'?",
        args.goal
    );

    let (selected_ref, prob, conf) = if args.model == "jpt" {
        query_jpt_decision(&state, &question, &options)?
    } else {
        query_imajev_decision(&state, &question, &options)?
    };

    let selected_desc = options
        .get(&selected_ref)
        .cloned()
        .unwrap_or_else(|| "Unknown".to_string());

    let mut actions = Vec::new();
    actions.push(UatAction {
        action: "click".to_string(),
        ref_id: selected_ref.clone(),
        description: selected_desc,
        probability: prob,
        confidence: conf,
        model: args.model.clone(),
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

    let verification = if errors.is_empty() {
        "verified_by_assertions".to_string()
    } else {
        "failed".to_string()
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
                "  Action: click {} ({}) [conf: {:.2}]",
                a.ref_id, a.description, a.confidence
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

fn query_jpt_decision(
    state: &str,
    question: &str,
    options: &HashMap<String, String>,
) -> Result<(String, f64, f64), Box<dyn std::error::Error>> {
    let payload = json!({
        "state": state,
        "question": question,
        "options": options,
        "mode": "choice"
    });

    let resp = ureq::post("http://127.0.0.1:8090/v1/decide")
        .timeout(Duration::from_millis(2500))
        .send_json(payload)?;

    let val: Value = resp.into_json()?;
    let answer = val
        .get("answer")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let conf = val.get("confidence").and_then(Value::as_f64).unwrap_or(0.9);
    let prob = val
        .get("probabilities")
        .and_then(|p| p.get(&answer))
        .and_then(Value::as_f64)
        .unwrap_or(0.9);

    Ok((answer, prob, conf))
}

fn query_imajev_decision(
    state: &str,
    question: &str,
    options: &HashMap<String, String>,
) -> Result<(String, f64, f64), Box<dyn std::error::Error>> {
    let prompt = format!(
        "State:\n{state}\n\nQuestion: {question}\n\nPick the best option key among:\n{}",
        options
            .iter()
            .map(|(k, v)| format!("- {k}: {v}"))
            .collect::<Vec<_>>()
            .join("\n")
    );

    let payload = json!({
        "model": "imajev-4b",
        "messages": [
            {"role": "system", "content": "You are a web automation decision engine. Reply only with the exact option key (e.g. uat-1)."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 16
    });

    let resp = ureq::post("http://127.0.0.1:8083/v1/chat/completions")
        .timeout(Duration::from_millis(2500))
        .send_json(payload)?;

    let val: Value = resp.into_json()?;
    let content = val
        .get("choices")
        .and_then(|c| c.get(0))
        .and_then(|c0| c0.get("message"))
        .and_then(|m| m.get("content"))
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim();

    for key in options.keys() {
        if content.contains(key) {
            return Ok((key.clone(), 0.95, 0.95));
        }
    }

    if let Some(first_key) = options.keys().next() {
        return Ok((first_key.clone(), 0.5, 0.5));
    }

    Err("No option found".into())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Daemon(d) => match d.action.as_str() {
            "start" => {
                ensure_cdp_daemon()?;
                println!(
                    "{}",
                    json!({"status": "running", "cdp_url": CDP_URL})
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
                let running = is_cdp_running();
                println!(
                    "{}",
                    json!({
                        "status": if running { "running" } else { "stopped" },
                        "cdp_url": CDP_URL
                    })
                );
            }
            _ => unreachable!(),
        },
        Commands::Verify(v) => run_verify(v)?,
        Commands::Uat(u) => run_uat(u)?,
        Commands::Snap(s) => run_snap(s)?,
        Commands::Nav(n) => run_nav(n)?,
    }
    Ok(())
}
