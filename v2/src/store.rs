//! Bounded extension-private persistence. No SDK detached blocking tasks.
use crate::discovery::{self, Font};
use serde::{Deserialize, Serialize};
use std::{
    io::{Read, Write},
    path::Path,
};
const MAX_STORE: usize = 256 * 1024;
#[derive(Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Preferences {
    #[serde(default)]
    pub pinned_fonts: Vec<String>,
    #[serde(default = "all")]
    pub filter: String,
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}
fn all() -> String {
    "all".into()
}
fn read(path: &Path, max: usize) -> Result<Option<Vec<u8>>, String> {
    let file = match std::fs::File::open(path) {
        Ok(f) => f,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(e) => return Err(format!("Cannot read private font data: {e}")),
    };
    let mut bytes = Vec::new();
    file.take((max + 1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > max {
        return Err("Private font data exceeds size limit".into());
    }
    Ok(Some(bytes))
}
pub fn preferences(dir: &Path) -> Result<Preferences, String> {
    let result: Preferences = match read(&dir.join("font-search/storage.json"), MAX_STORE)? {
        Some(b) => {
            serde_json::from_slice(&b).map_err(|e| format!("Invalid pinned font data: {e}"))?
        }
        None => Preferences {
            filter: all(),
            ..Default::default()
        },
    };
    if result.pinned_fonts.len() > discovery::MAX_FONTS
        || result
            .pinned_fonts
            .iter()
            .any(|s| s.len() > discovery::MAX_NAME)
        || !["all", "user"].contains(&result.filter.as_str())
    {
        return Err("Invalid pinned fonts/system-font filter".into());
    }
    Ok(result)
}
fn write(path: &Path, value: &impl Serialize, max: usize) -> Result<(), String> {
    let bytes = serde_json::to_vec(value).map_err(|e| e.to_string())?;
    if bytes.len() > max {
        return Err("Private font data exceeds size limit".into());
    }
    let parent = path.parent().ok_or("Invalid private font path")?;
    std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let mut tmp = tempfile::NamedTempFile::new_in(parent).map_err(|e| e.to_string())?;
    tmp.write_all(&bytes)
        .and_then(|()| tmp.as_file().sync_all())
        .map_err(|e| e.to_string())?;
    tmp.persist(path).map_err(|e| e.to_string())?;
    Ok(())
}
pub fn save_preferences(dir: &Path, prefs: &Preferences) -> Result<(), String> {
    write(&dir.join("font-search/storage.json"), prefs, MAX_STORE)
}
pub fn cache(dir: &Path) -> Result<Option<Vec<Font>>, String> {
    match read(
        &dir.join("font-search/installed-fonts.json"),
        discovery::MAX_CATALOG_BYTES,
    )? {
        None => Ok(None),
        Some(b) => {
            let fonts: Vec<Font> = serde_json::from_slice(&b)
                .map_err(|e| format!("Invalid installed font cache: {e}"))?;
            discovery::validate(&fonts)?;
            Ok(Some(fonts))
        }
    }
}
pub fn save_cache(dir: &Path, fonts: &[Font]) -> Result<(), String> {
    discovery::validate(fonts)?;
    write(
        &dir.join("font-search/installed-fonts.json"),
        &fonts,
        discovery::MAX_CATALOG_BYTES,
    )
}
pub fn clear_cache(dir: &Path) -> Result<(), String> {
    match std::fs::remove_file(dir.join("font-search/installed-fonts.json")) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}
