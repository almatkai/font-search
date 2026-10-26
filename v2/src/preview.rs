//! Same 600×300 SVG family lookup as V1. No font bytes copied or embedded.
use base64::{engine::general_purpose::STANDARD, Engine};
pub const MAX_TEXT: usize = 4096;
pub fn bounded(text: &str) -> Result<(), String> {
    if text.len() > MAX_TEXT
        || text
            .chars()
            .any(|c| matches!(c, '\0'..='\u{8}' | '\u{b}' | '\u{c}' | '\u{e}'..='\u{1f}'))
    {
        return Err(
            "Preview text exceeds 4096 UTF-8 bytes or contains XML control characters".into(),
        );
    }
    Ok(())
}
fn escape(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}
pub fn svg(name: &str, text: &str) -> Result<String, String> {
    bounded(text)?;
    if name.len() > crate::discovery::MAX_NAME {
        return Err("Preview font name exceeds limit".into());
    }
    bounded(name).map_err(|_| "Preview font name contains invalid XML controls")?;
    let name = escape(name);
    let mut svg = String::from("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"600\" height=\"300\"><style>text{font-size:24px;fill:#eeeeee;filter:saturate(0)}</style>");
    for (line, y) in [
        (text, 70),
        ("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 120),
        ("abcdefghijklmnopqrstuvwxyz", 170),
        ("0123456789!@#$%^()_+-={}[]:;", 220),
    ] {
        svg.push_str(&format!(
            "<text font-family=\"{name}\" x=\"10\" y=\"{y}\">{}</text>",
            escape(line)
        ));
    }
    svg.push_str("</svg>");
    Ok(svg)
}
pub fn markdown(name: &str, text: &str) -> Result<String, String> {
    Ok(format!(
        "![Font preview](data:image/svg+xml;base64,{})",
        STANDARD.encode(svg(name, text)?)
    ))
}
