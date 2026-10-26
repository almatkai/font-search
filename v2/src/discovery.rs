//! V1's portable producer: filenames, not invented OpenType metadata.
use icu_collator::{Collator, CollatorOptions};
use icu_locid::Locale;
use serde::{Deserialize, Serialize};
use std::{
    collections::HashSet,
    path::{Path, PathBuf},
};
use tezbar_extension_sdk::BoxFuture;

pub const MAX_FONTS: usize = 8192;
pub const MAX_ENTRIES: usize = 65536;
pub const MAX_DIRECTORIES: usize = 4096;
pub const MAX_PATH: usize = 4096;
pub const MAX_NAME: usize = 1024;
pub const MAX_CATALOG_BYTES: usize = 12 * 1024 * 1024;
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Font {
    pub name: String,
    pub path: String,
    pub is_system: bool,
    pub styles: Vec<String>,
    pub post_script_names: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Root {
    pub path: PathBuf,
    pub system: bool,
}
/// Pure root selection also used by the fixture oracle. No home traversal.
pub fn roots(
    platform: &str,
    home: &Path,
    windir: Option<&str>,
    local: Option<&str>,
) -> Result<Vec<Root>, String> {
    let pairs = match platform {
        "macOS" | "macos" | "darwin" => vec![
            (PathBuf::from("/System/Library/Fonts"), true),
            (PathBuf::from("/Library/Fonts"), true),
            (home.join("Library/Fonts"), false),
        ],
        "Windows" | "windows" | "win32" => vec![
            (
                PathBuf::from(windir.unwrap_or("C:\\Windows")).join("Fonts"),
                true,
            ),
            (
                local
                    .map(PathBuf::from)
                    .unwrap_or_else(|| home.join("AppData/Local"))
                    .join("Microsoft/Windows/Fonts"),
                false,
            ),
        ],
        _ => return Err("Font discovery supports macOS and Windows only".into()),
    };
    Ok(pairs
        .into_iter()
        .map(|(path, system)| Root { path, system })
        .collect())
}
pub fn from_path(path: &Path, system: bool) -> Result<Option<Font>, String> {
    let filename = path
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or("Font filename is not UTF-8")?;
    let dot = filename.rfind('.').filter(|i| *i > 0);
    let Some(dot) = dot else { return Ok(None) };
    if ![".ttf", ".otf", ".ttc", ".woff", ".woff2"]
        .contains(&filename[dot..].to_lowercase().as_str())
    {
        return Ok(None);
    }
    // JS /[-_]+/g: replace each run with ONE space, without trimming.
    let mut name = String::new();
    let mut in_separator = false;
    for c in filename[..dot].chars() {
        if c == '-' || c == '_' {
            if !in_separator {
                name.push(' ');
            }
            in_separator = true;
        } else {
            name.push(c);
            in_separator = false;
        }
    }
    let path = path.to_str().ok_or("Font path is not UTF-8")?.to_owned();
    if name.len() > MAX_NAME || path.len() > MAX_PATH {
        return Err("Font name/path exceeds limit".into());
    }
    Ok(Some(Font {
        styles: vec!["Regular".into()],
        post_script_names: vec![name.clone()],
        name,
        path,
        is_system: system,
    }))
}
pub fn validate(fonts: &[Font]) -> Result<(), String> {
    if fonts.len() > MAX_FONTS {
        return Err("Installed font count exceeds 8192; no partial catalog accepted".into());
    }
    let mut names = HashSet::new();
    for f in fonts {
        if f.name.len() > MAX_NAME
            || f.path.len() > MAX_PATH
            || f.name.starts_with('.')
            || !Path::new(&f.path).is_absolute()
            || f.styles != ["Regular"]
            || f.post_script_names != [f.name.clone()]
            || !names.insert(&f.name)
        {
            return Err("Invalid installed font cache (V1 filename metadata required)".into());
        }
    }
    if serde_json::to_vec(fonts).map_err(|e| e.to_string())?.len() > MAX_CATALOG_BYTES {
        return Err("Installed font metadata exceeds 12 MiB".into());
    }
    Ok(())
}
pub fn finish(fonts: Vec<Font>, locale: &str) -> Result<Vec<Font>, String> {
    let mut names = HashSet::new();
    let mut fonts: Vec<_> = fonts
        .into_iter()
        .filter(|f| names.insert(f.name.clone()))
        .filter(|f| !f.name.starts_with('.'))
        .collect();
    let locale: Locale = locale
        .replace('_', "-")
        .parse()
        .map_err(|_| "Invalid collation locale")?;
    let collator =
        Collator::try_new(&locale.into(), CollatorOptions::new()).map_err(|e| e.to_string())?;
    // Stable, first-root-wins Map semantics, ICU localeCompare-style collation.
    fonts.sort_by(|a, b| collator.compare(&a.name, &b.name));
    validate(&fonts)?;
    Ok(fonts)
}
pub trait Provider: Send + Sync + 'static {
    fn discover<'a>(&'a self, platform: &'a str) -> BoxFuture<'a, Result<Vec<Font>, String>>;
}
pub struct Native;
impl Provider for Native {
    fn discover<'a>(&'a self, platform: &'a str) -> BoxFuture<'a, Result<Vec<Font>, String>> {
        Box::pin(async move {
            // Read only explicit platform font roots, never the rest of home.
            let home = dirs::home_dir().ok_or("Cannot determine user home for font roots")?;
            let roots = roots(
                platform,
                Path::new(&home),
                std::env::var("WINDIR").ok().as_deref(),
                std::env::var("LOCALAPPDATA").ok().as_deref(),
            )?;
            if roots.iter().any(|root| !root.path.is_absolute()) {
                return Err("Platform font roots must be absolute".into());
            }
            let locale = sys_locale::get_locale().unwrap_or_else(|| "en-US".into());
            scan(&roots, &locale).await
        })
    }
}
/// Shared native filesystem producer; QA only supplies owned explicit roots.
pub async fn scan(roots: &[Root], locale: &str) -> Result<Vec<Font>, String> {
    let mut fonts = Vec::new();
    let mut entries_seen = 0;
    let mut dirs_seen = 0;
    for root in roots {
        let mut pending = vec![root.path.clone()];
        while let Some(directory) = pending.pop() {
            dirs_seen += 1;
            if dirs_seen > MAX_DIRECTORIES {
                return Err(
                    "Font enumeration exceeds 4096 directories; no partial catalog accepted".into(),
                );
            }
            // Same as V1: missing or protected directories are skipped. Other
            // failures are surfaced instead of silently hiding a partial catalog.
            let entries = match std::fs::read_dir(&directory) {
                Ok(entries) => entries,
                Err(e)
                    if matches!(
                        e.kind(),
                        std::io::ErrorKind::NotFound | std::io::ErrorKind::PermissionDenied
                    ) =>
                {
                    continue
                }
                Err(e) => return Err(format!("Error fetching fonts: {e}")),
            };
            let mut batch = Vec::new();
            for entry in entries {
                entries_seen += 1;
                if entries_seen > MAX_ENTRIES {
                    return Err(
                        "Font enumeration exceeds 65536 entries; no partial catalog accepted"
                            .into(),
                    );
                }
                let entry = entry.map_err(|e| format!("Error fetching fonts: {e}"))?;
                let filename = entry
                    .file_name()
                    .into_string()
                    .map_err(|_| "Font directory contains non-UTF-8 filename")?;
                batch.push((filename, entry));
            }
            // libuv scandir's sorted entries; stack retains depth-first LIFO order.
            batch.sort_by(|a, b| a.0.as_bytes().cmp(b.0.as_bytes()));
            for (_, entry) in batch {
                let path = entry.path();
                if path.to_str().is_none_or(|s| s.len() > MAX_PATH) {
                    return Err("Font path exceeds limit or is not UTF-8".into());
                }
                if entry.file_type().map_err(|e| e.to_string())?.is_dir() {
                    pending.push(path);
                } else if let Some(font) = from_path(&path, root.system)? {
                    fonts.push(font);
                }
                if fonts.len() > MAX_FONTS {
                    return Err(
                        "Font enumeration exceeds 8192 candidates; no partial catalog accepted"
                            .into(),
                    );
                }
            }
            // Cooperative cancellation without background enumeration or threads.
            tokio::task::yield_now().await;
        }
    }
    finish(fonts, locale)
}
