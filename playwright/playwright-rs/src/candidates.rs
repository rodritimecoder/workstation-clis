use playwright_upstream::Page;
use serde::{Deserialize, Serialize};
use std::error::Error;

type Result<T> = std::result::Result<T, Box<dyn Error>>;

const UAT_EXTRACT_JS: &str = r#"
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
            elements.push({ ref, description: `${role} '${text}'` });
        }
    }
    return elements;
})()
"#;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(super) struct Candidate {
    pub(super) r#ref: String,
    pub(super) description: String,
}

pub(super) async fn extract_candidates(page: &Page) -> Result<Vec<Candidate>> {
    Ok(page.evaluate::<(), Vec<Candidate>>(UAT_EXTRACT_JS, None).await?)
}
