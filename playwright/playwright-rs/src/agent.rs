use clap::{Args, Parser, Subcommand};
mod candidates;
mod decisions;
use candidates::{extract_candidates, Candidate};
use decisions::{query_imajev_decision, query_jpt_decision};
use playwright_upstream::protocol::{
    AriaSnapshotMode, AriaSnapshotOptions, ClickOptions, FillOptions, GotoOptions,
    KeyboardOptions, WaitForFunctionOptions,
};
use playwright_upstream::{Browser, ConnectOverCdpOptions, Page, Playwright};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::HashMap;
use std::error::Error;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, ExitCode};
use std::time::{Duration, Instant};

type Result<T> = std::result::Result<T, Box<dyn Error>>;

const DEFAULT_PORT: u16 = 9222;
#[derive(Parser)]
#[command(name = "playwright-rs", about = "Playwright browser automation for agents")]
struct Cli {
    #[arg(short = 's', long, global = true, default_value = "default")]
    session: String,
    #[arg(long, global = true, default_value_t = DEFAULT_PORT)]
    port: u16,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Daemon(DaemonArgs),
    Verify(VerifyArgs),
    Uat(UatArgs),
    Candidates(CandidatesArgs),
    Snap(UrlArgs),
    Nav(NavArgs),
    Open(OpenArgs),
    Attach(AttachArgs),
    Goto(GotoArgs),
    Snapshot(JsonArgs),
    Click(ClickArgs),
    Fill(FillArgs),
    Type(FillArgs),
    Press(PressArgs),
    Eval(EvalArgs),
    Screenshot(ScreenshotArgs),
    Close(JsonArgs),
}

#[derive(Args)]
struct DaemonArgs {
    #[arg(value_parser = ["start", "stop", "status"])]
    action: String,
}

#[derive(Args)]
struct JsonArgs {
    #[arg(long, default_value_t = false)]
    json: bool,
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
    #[arg(long = "ref")]
    ref_id: Option<String>,
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
struct UrlArgs {
    url: String,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    json: bool,
}

#[derive(Args)]
struct CandidatesArgs {
    url: String,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long, default_value_t = false)]
    no_block_media: bool,
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
struct ClickArgs {
    target: String,
    #[arg(long, default_value_t = 5000)]
    timeout: u64,
    #[arg(long)]
    expect_text: Option<String>,
    #[arg(long)]
    expect_url: Option<String>,
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

#[derive(Serialize, Deserialize, Default)]
struct Session {
    #[serde(default)]
    cdp_url: String,
    #[serde(default)]
    cdp_port: u16,
    #[serde(default)]
    url: String,
    #[serde(default)]
    page_index: Option<usize>,
}

struct Client {
    playwright: Playwright,
    browser: Browser,
    page: Page,
    page_index: usize,
    ephemeral: bool,
}

impl Client {
    async fn connect(
        endpoint: &str,
        preferred_url: Option<&str>,
        preferred_index: Option<usize>,
        create_page: bool,
        timeout_ms: u64,
    ) -> Result<Self> {
        let playwright = Playwright::launch().await?;
        let options = ConnectOverCdpOptions::new().timeout(timeout_ms as f64);
        let browser = playwright
            .chromium()
            .connect_over_cdp(endpoint, Some(options))
            .await?;
        let contexts = browser.contexts();
        let mut pages = contexts.iter().flat_map(|context| context.pages()).collect::<Vec<_>>();
        let (page, page_index) = if create_page {
            let index = pages.len();
            let page = match contexts.first() {
                Some(context) => context.new_page().await?,
                None => browser.new_page().await?,
            };
            (page, index)
        } else if let Some(index) = preferred_url
            .and_then(|url| pages.iter().position(|page| page.url() == url))
        {
            (pages.swap_remove(index), index)
        } else if let Some(index) = preferred_index.filter(|index| *index < pages.len()) {
            (pages.swap_remove(index), index)
        } else {
            pages
                .drain(..)
                .next()
                .map(|page| (page, 0))
                .ok_or("No page target found on the CDP endpoint")?
        };
        page.set_default_timeout(timeout_ms as f64).await;
        Ok(Self {
            playwright,
            browser,
            page,
            page_index,
            ephemeral: false,
        })
    }

}

fn session_path(name: &str) -> Result<PathBuf> {
    if name.is_empty() || !name.chars().all(|ch| ch.is_ascii_alphanumeric() || "-_".contains(ch)) {
        return Err("session names may contain only letters, numbers, hyphens, and underscores".into());
    }
    Ok(std::env::temp_dir().join(format!("fast_cdp_session_{name}.json")))
}

fn load_session(name: &str, port: u16) -> Result<Session> {
    let path = session_path(name)?;
    match fs::read_to_string(path) {
        Ok(contents) => {
            let mut session: Session = serde_json::from_str(&contents)?;
            if session.cdp_url.is_empty() {
                let stored_port = if session.cdp_port == 0 { port } else { session.cdp_port };
                session.cdp_url = endpoint(stored_port);
            }
            Ok(session)
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(Session {
            cdp_url: endpoint(port),
            cdp_port: port,
            ..Session::default()
        }),
        Err(error) => Err(error.into()),
    }
}

fn save_session(name: &str, session: &Session) -> Result<()> {
    fs::write(session_path(name)?, serde_json::to_vec_pretty(session)?)?;
    Ok(())
}

fn endpoint(port: u16) -> String {
    format!("http://127.0.0.1:{port}")
}

fn normalize_url(url: &str) -> String {
    if url == "about:blank"
        || url.starts_with("http://")
        || url.starts_with("https://")
        || url.starts_with("file:")
        || url.starts_with("data:")
    {
        url.to_string()
    } else {
        format!("https://{url}")
    }
}

fn save_client_session(name: &str, client: &Client, endpoint: &str, port: u16) -> Result<()> {
    save_session(
        name,
        &Session {
            cdp_url: endpoint.to_string(),
            cdp_port: port,
            url: client.page.url(),
            page_index: Some(client.page_index),
        },
    )
}

async fn finish<T>(client: Client, result: Result<T>) -> Result<T> {
    if client.ephemeral {
        let _ = client.page.close().await;
    }
    let _connected = client.browser.is_connected();
    let shutdown = client.playwright.shutdown().await;
    match result {
        Err(error) => Err(error),
        Ok(value) => {
            shutdown?;
            Ok(value)
        }
    }
}

fn legacy_binary() -> Result<PathBuf> {
    let executable = std::env::current_exe()?;
    let path = executable.with_file_name("legacy-fast-cdp");
    if path.is_file() {
        Ok(path)
    } else {
        Err(format!("legacy browser launcher is missing: {}", path.display()).into())
    }
}

fn run_daemon(action: &str, port: u16) -> Result<()> {
    let status = Command::new(legacy_binary()?)
        .args(["--port", &port.to_string(), "daemon", action])
        .status()?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("daemon {action} failed with {status}").into())
    }
}

fn ensure_daemon(port: u16) -> Result<()> {
    let status = Command::new(legacy_binary()?)
        .args(["--port", &port.to_string(), "daemon", "start"])
        .output()?;
    if status.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&status.stderr).trim().to_string().into())
    }
}

async fn block_lightweight_assets(page: &Page) -> Result<()> {
    page.route("**/*", |route| async move {
        let url = route.request().url().to_ascii_lowercase();
        let blocked = [".woff", ".ttf", "analytics", "googletagmanager"]
            .iter()
            .any(|part| url.contains(part));
        if blocked {
            route.abort(None).await
        } else {
            route.continue_(None).await
        }
    })
    .await?;
    Ok(())
}

fn target_locator(page: &Page, target: &str) -> playwright_upstream::protocol::Locator {
    let target = target.trim();
    if target.starts_with('e') && target.len() > 1 && target[1..].chars().all(|ch| ch.is_ascii_digit()) {
        page.get_by_ref(target)
    } else if let Some(reference) = target.strip_prefix("ref=") {
        page.get_by_ref(reference)
    } else if target.starts_with("uat-") {
        page.locator(format!("[data-uat-ref=\"{target}\"]"))
    } else {
        page.locator(target)
    }
}

async fn refresh_ai_ref(page: &Page, target: &str) -> Result<()> {
    let reference = target.strip_prefix("ref=").unwrap_or(target);
    if reference.starts_with('e')
        && reference.len() > 1
        && reference[1..].chars().all(|ch| ch.is_ascii_digit())
    {
        let snapshot = page
            .aria_snapshot(Some(AriaSnapshotOptions::default().mode(AriaSnapshotMode::Ai)))
            .await?;
        if !snapshot.contains(&format!("[ref={reference}]")) {
            return Err(format!("ref '{reference}' is not in the current accessibility snapshot").into());
        }
    }
    Ok(())
}

async fn navigate(page: &Page, url: &str, timeout_ms: u64) -> Result<()> {
    let options = GotoOptions::new().timeout(Duration::from_millis(timeout_ms));
    page.goto(&normalize_url(url), Some(options)).await?;
    Ok(())
}

async fn wait_for_effects(
    page: &Page,
    expect_text: Option<&str>,
    expect_url: Option<&str>,
    timeout_ms: u64,
) -> Result<Vec<String>> {
    let mut effects = Vec::new();
    if let Some(text) = expect_text {
        let expression = format!(
            "() => document.body && document.body.innerText.includes({})",
            serde_json::to_string(text)?
        );
        page.wait_for_function(
            &expression,
            Some(WaitForFunctionOptions::default().timeout(timeout_ms as f64)),
        )
        .await
        .map_err(|error| format!("clicked, but text '{text}' never appeared within {timeout_ms}ms: {error}"))?;
        effects.push(format!("text:{text}"));
    }
    if let Some(url) = expect_url {
        let expression = format!(
            "() => location.href.includes({})",
            serde_json::to_string(url)?
        );
        page.wait_for_function(
            &expression,
            Some(WaitForFunctionOptions::default().timeout(timeout_ms as f64)),
        )
        .await
        .map_err(|error| format!("clicked, but URL never contained '{url}' within {timeout_ms}ms: {error}"))?;
        effects.push(format!("url:{url}"));
    }
    Ok(effects)
}

async fn print_snapshot(page: &Page, json_output: bool) -> Result<()> {
    let text = page
        .aria_snapshot(Some(AriaSnapshotOptions::default().mode(AriaSnapshotMode::Ai)))
        .await?;
    let mut elements = Vec::new();
    for line in text.lines() {
        let Some((description, reference)) = line.rsplit_once("[ref=") else {
            continue;
        };
        let Some(reference) = reference.split(']').next() else {
            continue;
        };
        elements.push(json!({
            "ref": reference,
            "description": description.trim().trim_start_matches("- "),
        }));
    }
    let snapshot = json!({
        "url": page.url(),
        "title": page.title().await?,
        "text": text,
        "elements": elements,
    });
    if json_output {
        println!("{}", serde_json::to_string_pretty(&snapshot)?);
    } else {
        println!("Page: {} ({})\n---\n{}", snapshot["title"].as_str().unwrap_or(""), snapshot["url"].as_str().unwrap_or(""), snapshot["text"].as_str().unwrap_or(""));
    }
    Ok(())
}

async fn emit_candidates(page: &Page, json_output: bool) -> Result<Vec<Candidate>> {
    let candidates = extract_candidates(page).await?;
    if json_output {
        println!("{}", serde_json::to_string_pretty(&candidates)?);
    } else {
        for candidate in &candidates {
            println!("{}: {}", candidate.r#ref, candidate.description);
        }
    }
    Ok(candidates)
}

async fn run_open(args: OpenArgs, name: &str, port: u16) -> Result<()> {
    ensure_daemon(port)?;
    let endpoint = endpoint(port);
    let result = async {
        let client = Client::connect(&endpoint, None, None, true, args.timeout).await?;
        if !args.no_block_media {
            block_lightweight_assets(&client.page).await?;
        }
        let url = args.url.as_deref().unwrap_or("about:blank");
        if url != "about:blank" {
            navigate(&client.page, url, args.timeout).await?;
        }
        let title = client.page.title().await?;
        save_client_session(name, &client, &endpoint, port)?;
        if args.json {
            println!("{}", json!({"status":"opened","session":name,"url":client.page.url(),"title":title}));
        } else {
            println!("Opened browser session [{name}]: {} - {title}", client.page.url());
            println!("Ready for: snapshot, click, fill, type, press, eval, screenshot, close");
        }
        finish(client, Ok(())).await
    };
    result.await
}

async fn run_attach(args: AttachArgs, name: &str, port: u16) -> Result<()> {
    let cdp_url = args.cdp.unwrap_or_else(|| endpoint(port));
    let client = Client::connect(&cdp_url, None, None, false, 5000).await?;
    save_client_session(name, &client, &cdp_url, port)?;
    if args.json {
        println!("{}", json!({"status":"attached","session":name,"url":client.page.url()}));
    } else {
        println!("Attached to session [{name}]: {}", client.page.url());
    }
    finish(client, Ok(())).await
}

async fn connect_session(name: &str, port: u16, timeout: u64) -> Result<(Client, Session)> {
    let session = load_session(name, port)?;
    let client = Client::connect(
        &session.cdp_url,
        (!session.url.is_empty()).then_some(session.url.as_str()),
        session.page_index,
        false,
        timeout,
    )
    .await?;
    Ok((client, session))
}

async fn run_goto(args: GotoArgs, name: &str, port: u16) -> Result<()> {
    let (client, mut session) = connect_session(name, port, args.timeout).await?;
    let result = async {
        navigate(&client.page, &args.url, args.timeout).await?;
        session.url = client.page.url();
        session.page_index = Some(client.page_index);
        save_session(name, &session)?;
        let title = client.page.title().await?;
        if args.json {
            println!("{}", json!({"status":"navigated","session":name,"url":session.url,"title":title}));
        } else {
            println!("Navigated [{name}]: {} - {title}", session.url);
        }
        Ok(())
    }
    .await;
    finish(client, result).await
}

async fn run_snapshot(args: JsonArgs, name: &str, port: u16) -> Result<()> {
    let (client, _) = connect_session(name, port, 5000).await?;
    let result = print_snapshot(&client.page, args.json).await;
    finish(client, result).await
}

async fn run_click(args: ClickArgs, name: &str, port: u16) -> Result<()> {
    let (client, _) = connect_session(name, port, args.timeout).await?;
    let started = Instant::now();
    let result = async {
        refresh_ai_ref(&client.page, &args.target).await?;
        let locator = target_locator(&client.page, &args.target);
        let options = ClickOptions::builder().timeout(args.timeout as f64).build();
        if let Err(error) = locator.click(Some(options)).await {
            let detail = error.to_string();
            let disabled = locator.is_disabled().await.unwrap_or(false);
            let hit = locator
                .evaluate::<Value, ()>(
                    "el => { const r = el.getBoundingClientRect(); const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return { covered: !!top && top !== el && !el.contains(top), by: top?.tagName?.toLowerCase() || '' }; }",
                    None,
                )
                .await
                .unwrap_or(Value::Null);
            let state = if disabled {
                "element is disabled".to_string()
            } else if hit["covered"].as_bool() == Some(true) {
                format!("covered by {}", hit["by"].as_str().unwrap_or("another element"))
            } else {
                detail
            };
            return Err(format!(
                "{} was never clickable within {}ms ({state})",
                args.target, args.timeout
            )
            .into());
        }
        let effects = wait_for_effects(
            &client.page,
            args.expect_text.as_deref(),
            args.expect_url.as_deref(),
            args.timeout,
        )
        .await?;
        let waited_ms = started.elapsed().as_millis();
        if args.json {
            println!("{}", json!({"ok":true,"waited_ms":waited_ms,"effects":effects,"url":client.page.url()}));
        } else {
            println!("Clicked: {} after {waited_ms}ms", args.target);
        }
        Ok(())
    }
    .await;
    finish(client, result).await
}

async fn run_fill(args: FillArgs, name: &str, port: u16) -> Result<()> {
    let (client, _) = connect_session(name, port, args.timeout).await?;
    let result = async {
        refresh_ai_ref(&client.page, &args.target).await?;
        let locator = target_locator(&client.page, &args.target);
        let options = FillOptions::builder().timeout(args.timeout as f64).build();
        locator.fill(&args.text, Some(options)).await?;
        if args.json {
            println!("{}", json!({"ok":true,"target":args.target,"text":args.text}));
        } else {
            println!("Filled: {} with \"{}\"", args.target, args.text);
        }
        Ok(())
    }
    .await;
    finish(client, result).await
}

async fn run_press(args: PressArgs, name: &str, port: u16) -> Result<()> {
    let (client, _) = connect_session(name, port, 5000).await?;
    let result = async {
        client
            .page
            .keyboard()
            .press(&args.key, Some(KeyboardOptions::default()))
            .await?;
        if args.json {
            println!("{}", json!({"status":"pressed","key":args.key}));
        } else {
            println!("Pressed: {}", args.key);
        }
        Ok(())
    }
    .await;
    finish(client, result).await
}

async fn run_eval(args: EvalArgs, name: &str, port: u16) -> Result<()> {
    let (client, _) = connect_session(name, port, 5000).await?;
    let result = async {
        let value = client.page.evaluate::<(), Value>(&args.expr, None).await?;
        if args.json {
            println!("{}", serde_json::to_string_pretty(&value)?);
        } else if let Some(text) = value.as_str() {
            println!("{text}");
        } else {
            println!("{value}");
        }
        Ok(())
    }
    .await;
    finish(client, result).await
}

async fn run_screenshot(args: ScreenshotArgs, name: &str, port: u16) -> Result<()> {
    let (client, _) = connect_session(name, port, 5000).await?;
    let result = async {
        let path = args.path.unwrap_or_else(|| std::env::temp_dir().join(format!("fast_cdp_{name}.png")));
        client.page.screenshot_to_file(&path, None).await?;
        if args.json {
            println!("{}", json!({"status":"saved","path":path.display().to_string()}));
        } else {
            println!("Screenshot saved: {}", path.display());
        }
        Ok(())
    }
    .await;
    finish(client, result).await
}

async fn run_close(args: JsonArgs, name: &str, port: u16) -> Result<()> {
    let result = async {
        if let Ok((client, _)) = connect_session(name, port, 1500).await {
            let closed = client.page.close().await;
            let _ = client.playwright.shutdown().await;
            closed?;
        }
        if let Ok(path) = session_path(name) {
            let _ = fs::remove_file(path);
        }
        if args.json {
            println!("{}", json!({"status":"closed","session":name}));
        } else {
            println!("Closed session [{name}]");
        }
        Ok(())
    };
    result.await
}

async fn one_shot_page(port: u16, url: &str, timeout: u64, block: bool) -> Result<Client> {
    ensure_daemon(port)?;
    let mut client = Client::connect(&endpoint(port), None, None, true, timeout).await?;
    client.ephemeral = true;
    if block {
        block_lightweight_assets(&client.page).await?;
    }
    navigate(&client.page, url, timeout).await?;
    Ok(client)
}

async fn run_snap(args: UrlArgs, port: u16) -> Result<()> {
    let client = one_shot_page(port, &args.url, args.timeout, true).await?;
    let result = async {
        let text: String = client.page.locator("body").inner_text().await.unwrap_or_default();
        let title = client.page.title().await?;
        let output = json!({"url":client.page.url(),"title":title,"text":text});
        if args.json {
            println!("{}", serde_json::to_string_pretty(&output)?);
        } else {
            println!("Title: {title}\nURL: {}\n---\n{text}", client.page.url());
        }
        Ok(())
    }
    .await;
    finish(client, result).await
}

async fn run_nav(args: NavArgs, port: u16) -> Result<()> {
    ensure_daemon(port)?;
    let mut client = Client::connect(&endpoint(port), None, None, true, args.timeout).await?;
    client.ephemeral = true;
    let result = async {
        navigate(&client.page, &args.url, args.timeout).await?;
        let title = client.page.title().await?;
        if let Some(path) = &args.screenshot_path {
            client.page.screenshot_to_file(path, None).await?;
        }
        if args.json {
            println!("{}", json!({"url":client.page.url(),"title":title,"screenshot":args.screenshot_path.as_ref().map(|path|path.display().to_string())}));
        } else {
            println!("Navigated to {} - {title}", client.page.url());
        }
        Ok(())
    }
    .await;
    finish(client, result).await
}

async fn run_candidates(args: CandidatesArgs, port: u16) -> Result<()> {
    let client = one_shot_page(port, &args.url, args.timeout, !args.no_block_media).await?;
    let result = emit_candidates(&client.page, args.json).await.map(|_| ());
    finish(client, result).await
}

async fn run_verify(args: VerifyArgs, port: u16) -> Result<()> {
    let started = Instant::now();
    let client = one_shot_page(port, &args.url, args.timeout, !args.no_block_media).await?;
    let result = async {
        let mut passed_checks = Vec::new();
        let mut errors = Vec::new();
        let mut eval_result = None;
        if let Some(selector) = args.click_selector.as_deref() {
            refresh_ai_ref(&client.page, selector).await?;
            match target_locator(&client.page, selector).click(Some(ClickOptions::builder().timeout(args.timeout as f64).build())).await {
                Ok(()) => passed_checks.push(format!("click:{selector}")),
                Err(error) => errors.push(error.to_string()),
            }
        }
        if let (Some(target), Some(text)) = (args.type_target.as_deref(), args.type_text.as_deref()) {
            refresh_ai_ref(&client.page, target).await?;
            match target_locator(&client.page, target).fill(text, Some(FillOptions::builder().timeout(args.timeout as f64).build())).await {
                Ok(()) => passed_checks.push(format!("type:{target}")),
                Err(error) => errors.push(error.to_string()),
            }
        }
        if let Some(selector) = args.assert_selector.as_deref() {
            match client.page.locator(selector).count().await {
                Ok(count) if count > 0 => passed_checks.push(format!("selector:{selector}")),
                Ok(_) => errors.push(format!("Selector '{selector}' did not exist in DOM")),
                Err(error) => errors.push(error.to_string()),
            }
        }
        if let Some(text) = args.assert_text.as_deref() {
            match wait_for_effects(&client.page, Some(text), None, args.timeout).await {
                Ok(_) => passed_checks.push(format!("text:{text}")),
                Err(error) => errors.push(error.to_string()),
            }
        }
        if let Some(expression) = args.eval_script.as_deref() {
            match client.page.evaluate::<(), Value>(expression, None).await {
                Ok(value) => {
                    eval_result = Some(value);
                    passed_checks.push(format!("eval:{expression}"));
                }
                Err(error) => errors.push(error.to_string()),
            }
        }
        if let Some(path) = args.screenshot_path.as_ref() {
            match client.page.screenshot_to_file(path, None).await {
                Ok(_) => passed_checks.push(format!("screenshot:{}", path.display())),
                Err(error) => errors.push(error.to_string()),
            }
        }
        let title = client.page.title().await?;
        let duration_ms = started.elapsed().as_secs_f64() * 1000.0;
        let ok = errors.is_empty();
        let output = json!({
            "ok": ok,
            "url": client.page.url(),
            "title": title,
            "duration_ms": duration_ms,
            "passed_checks": &passed_checks,
            "errors": &errors,
            "eval_result": eval_result,
        });
        if args.json {
            println!("{}", serde_json::to_string_pretty(&output)?);
        } else {
            println!("[{}] {} ({duration_ms:.1}ms)", if ok { "PASS" } else { "FAIL" }, client.page.url());
            for check in &passed_checks { println!("  ✓ {check}"); }
            for error in &errors { eprintln!("  ✗ {error}"); }
        }
        if !ok {
            return Err("verification failed".into());
        }
        Ok(())
    }
    .await;
    finish(client, result).await
}

async fn run_uat(args: UatArgs, port: u16) -> Result<()> {
    let started = Instant::now();
    let client = one_shot_page(port, &args.url, args.timeout, !args.no_block_media).await?;
    let result = async {
        let candidates = extract_candidates(&client.page).await?;
        if candidates.is_empty() {
            return Err(format!("No interactive elements found on page: {}", client.page.url()).into());
        }
        let options = candidates.iter().take(20).map(|candidate| {
            (candidate.r#ref.clone(), candidate.description.clone())
        }).collect::<HashMap<_, _>>();
        let selected = if let Some(reference) = args.ref_id.clone() {
            if !options.contains_key(&reference) {
                return Err(format!("ref '{reference}' is not on this page. Available: {}", options.keys().cloned().collect::<Vec<_>>().join(", ")).into());
            }
            (reference, 1.0, 1.0, "external".to_string())
        } else if args.model == "jpt" {
            let state = format!("Page Title: {}\nURL: {}\nGoal: {}\nInteractive Elements:\n{}", client.page.title().await?, client.page.url(), args.goal, options.iter().map(|(reference, description)|format!("- {reference}: {description}")).collect::<Vec<_>>().join("\n"));
            let question = format!("Which interactive element should be clicked or triggered to achieve: '{}' ?", args.goal);
            query_jpt_decision(&state, &question, &options)?
        } else {
            let state = format!("Page Title: {}\nURL: {}\nGoal: {}", client.page.title().await?, client.page.url(), args.goal);
            let question = format!("Which interactive element should be clicked or triggered to achieve: '{}' ?", args.goal);
            query_imajev_decision(&state, &question, &options)?
        };
        let (reference, probability, confidence, model) = selected;
        let description = options.get(&reference).cloned().unwrap_or_default();
        let action = UatAction { action: "click".into(), ref_id: reference.clone(), description, probability, confidence, model };
        let mut errors = Vec::new();
        let click = target_locator(&client.page, &reference)
            .click(Some(ClickOptions::builder().timeout(args.timeout as f64).build()))
            .await;
        let effects = match click {
            Ok(()) => match wait_for_effects(&client.page, args.expect_text.as_deref(), args.expect_url.as_deref(), args.timeout).await {
                Ok(effects) => effects,
                Err(error) => {
                    errors.push(error.to_string());
                    Vec::new()
                }
            },
            Err(error) => {
                errors.push(error.to_string());
                Vec::new()
            }
        };
        let verification = if args.expect_text.is_some() || args.expect_url.is_some() { "verified_by_assertions" } else { "action_executed" };
        if let Some(path) = args.screenshot_path.as_ref() {
            if let Err(error) = client.page.screenshot_to_file(path, None).await {
                errors.push(error.to_string());
            }
        }
        let duration_ms = (started.elapsed().as_secs_f64() * 1000.0 * 100.0).round() / 100.0;
        let output = UatResult { ok: errors.is_empty(), url: client.page.url(), goal: args.goal.clone(), duration_ms, actions: vec![action], verification: verification.into(), errors };
        if args.json {
            println!("{}", serde_json::to_string_pretty(&output)?);
        } else {
            println!("[{}] UAT: {} ({duration_ms:.1}ms)", if output.ok { "PASS" } else { "FAIL" }, output.goal);
            println!("  Action: click {} ({}) [conf: {:.2}]", output.actions[0].ref_id, output.actions[0].description, output.actions[0].confidence);
            if !effects.is_empty() { println!("  Verified: {}", effects.join(", ")); }
            for error in &output.errors { eprintln!("  ✗ {error}"); }
        }
        if output.ok { Ok(()) } else { Err("UAT failed".into()) }
    }
    .await;
    finish(client, result).await
}

#[tokio::main]
async fn main() -> ExitCode {
    match run(Cli::parse()).await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("playwright-rs: {error}");
            ExitCode::FAILURE
        }
    }
}

async fn run(cli: Cli) -> Result<()> {
    let name = cli.session.as_str();
    let port = cli.port;
    match cli.command {
        Commands::Daemon(args) => run_daemon(&args.action, port),
        Commands::Open(args) => run_open(args, name, port).await,
        Commands::Attach(args) => run_attach(args, name, port).await,
        Commands::Goto(args) => run_goto(args, name, port).await,
        Commands::Snapshot(args) => run_snapshot(args, name, port).await,
        Commands::Click(args) => run_click(args, name, port).await,
        Commands::Fill(args) | Commands::Type(args) => run_fill(args, name, port).await,
        Commands::Press(args) => run_press(args, name, port).await,
        Commands::Eval(args) => run_eval(args, name, port).await,
        Commands::Screenshot(args) => run_screenshot(args, name, port).await,
        Commands::Close(args) => run_close(args, name, port).await,
        Commands::Verify(args) => run_verify(args, port).await,
        Commands::Uat(args) => run_uat(args, port).await,
        Commands::Candidates(args) => run_candidates(args, port).await,
        Commands::Snap(args) => run_snap(args, port).await,
        Commands::Nav(args) => run_nav(args, port).await,
    }
}
