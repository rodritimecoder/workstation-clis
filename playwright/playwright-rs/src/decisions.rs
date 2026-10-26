use serde_json::{Value, json};
use std::collections::HashMap;
use std::error::Error;
use std::time::Duration;

type Result<T> = std::result::Result<T, Box<dyn Error>>;

pub(super) fn query_jpt_decision(
    state: &str,
    question: &str,
    options: &HashMap<String, String>,
) -> Result<(String, f64, f64, String)> {
    let response = ureq::post("http://127.0.0.1:8090/v1/decide")
        .timeout(Duration::from_millis(2500))
        .send_json(json!({
            "state": state,
            "question": question,
            "options": options,
            "mode": "choice"
        }))?;
    let value: Value = response.into_json()?;
    let answer = value
        .get("answer")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let confidence = value
        .get("confidence")
        .and_then(Value::as_f64)
        .unwrap_or(0.9);
    let probability = value
        .get("probabilities")
        .and_then(|items| items.get(&answer))
        .and_then(Value::as_f64)
        .unwrap_or(0.9);
    if !options.contains_key(&answer) {
        return Err(format!("decision model selected unknown ref '{answer}'").into());
    }
    Ok((answer, probability, confidence, "jpt".into()))
}

pub(super) fn query_imajev_decision(
    state: &str,
    question: &str,
    options: &HashMap<String, String>,
) -> Result<(String, f64, f64, String)> {
    let options_text = options
        .iter()
        .map(|(key, value)| format!("- {key}: {value}"))
        .collect::<Vec<_>>()
        .join("\n");
    let prompt = format!(
        "State:\n{state}\n\nQuestion: {question}\n\nPick the best option key among:\n{options_text}"
    );
    let response = ureq::post("http://127.0.0.1:8083/v1/chat/completions")
        .timeout(Duration::from_millis(2500))
        .send_json(json!({
            "model": "imajev-4b",
            "messages": [
                {"role": "system", "content": "You are a web automation decision engine. Reply only with the exact option key (e.g. uat-1)."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 16
        }))?;
    let value: Value = response.into_json()?;
    let content = value
        .pointer("/choices/0/message/content")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim();
    let selected = options
        .keys()
        .find(|key| content.contains(key.as_str()))
        .cloned()
        .ok_or("decision model returned no valid candidate")?;
    Ok((selected, 0.95, 0.95, "imajev".into()))
}
