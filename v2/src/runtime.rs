use crate::{
    discovery::{self, Font, Provider},
    preview, store, DEFAULT_PREVIEW, ID, VERSION,
};
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    future::Future,
    pin::Pin,
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc, Mutex,
    },
    task::{Context, Poll, Waker},
};
use tezbar_extension_sdk::{BoxFuture, CoreResult, Extension, ExtensionContext};
use tokio::sync::Mutex as AsyncMutex;
const PAGE: usize = 64;
const MAX_VISIBLE: usize = 256;
const MAX_QUERY: usize = 4096;
const MAX_SESSIONS: usize = 128;
const MAX_VIEW: usize = 12 * 1024 * 1024;
#[derive(Clone)]
enum Action {
    Copy(String, &'static str),
    Reveal(String),
    Names(Font),
    Pin(String),
    Reload,
    Back,
    Retry,
    Dismiss,
}
#[derive(Clone)]
struct Effect {
    method: &'static str,
    params: Value,
    title: &'static str,
}
struct Session {
    token: u64,
    revision: u64,
    draft_revision: u64,
    query: String,
    font_query: String,
    filter: String,
    preview: String,
    names: Option<Font>,
    limit: usize,
    actions: HashMap<String, Action>,
    pending: Option<Effect>,
    message: Option<String>,
}
struct Entry {
    token: u64,
    cancel: Pin<Box<dyn Future<Output = ()> + Send>>,
    value: Arc<AsyncMutex<Session>>,
}
type Registry = Arc<Mutex<HashMap<String, Entry>>>;
fn prune(map: &mut HashMap<String, Entry>) {
    let mut cx = Context::from_waker(Waker::noop());
    map.retain(|_, entry| !matches!(entry.cancel.as_mut().poll(&mut cx), Poll::Ready(())));
}
struct OpenGuard {
    registry: Registry,
    id: String,
    token: u64,
    armed: bool,
}
impl Drop for OpenGuard {
    fn drop(&mut self) {
        if self.armed {
            if let Ok(mut map) = self.registry.lock() {
                if map.get(&self.id).is_some_and(|e| e.token == self.token) {
                    map.remove(&self.id);
                }
            }
        }
    }
}
pub struct Adapter {
    provider: Arc<dyn Provider>,
    registry: Registry,
    next: AtomicU64,
    catalog: AsyncMutex<Option<Result<Arc<Vec<Font>>, String>>>,
    persistence: AsyncMutex<()>,
}
impl Adapter {
    pub fn production() -> Self {
        Self::new(Arc::new(discovery::Native))
    }
    fn new(provider: Arc<dyn Provider>) -> Self {
        Self {
            provider,
            registry: Arc::default(),
            next: AtomicU64::new(1),
            catalog: AsyncMutex::new(None),
            persistence: AsyncMutex::new(()),
        }
    }
    /// Compiled only into tests/the separate QA binary. No production override.
    #[cfg(any(test, feature = "qa"))]
    pub fn with_fixture_provider(provider: Arc<dyn Provider>) -> Self {
        Self::new(provider)
    }
    fn serial(&self) -> u64 {
        self.next.fetch_add(1, Ordering::Relaxed)
    }
    async fn catalog(
        &self,
        ctx: &ExtensionContext,
        reload: bool,
    ) -> Result<Arc<Vec<Font>>, String> {
        let mut cache = self.catalog.lock().await;
        if reload {
            store::clear_cache(&ctx.paths.data_dir)?;
            *cache = None;
        }
        if let Some(fonts) = cache.as_ref() {
            return fonts.clone();
        }
        let result = async {
            let fonts = if !reload { store::cache(&ctx.paths.data_dir)? } else { None };
            let fonts = match fonts {
                Some(fonts) => fonts,
                None => {
                    let fonts = self.provider.discover(&ctx.platform).await?;
                    discovery::validate(&fonts)?;
                    tokio::select! { biased; _=ctx.cancelled()=>return Err("Font discovery cancelled".into()), _=std::future::ready(())=>{} }
                    store::save_cache(&ctx.paths.data_dir, &fonts)?;
                    fonts
                }
            };
            Ok(Arc::new(fonts))
        }.await;
        // Failed discovery is retried only by the deliberate Reload action.
        *cache = Some(result.clone());
        result
    }

    fn register(
        &self,
        ctx: &ExtensionContext,
        payload: &Value,
    ) -> Result<(Arc<AsyncMutex<Session>>, OpenGuard), String> {
        let id = payload["sessionId"]
            .as_str()
            .filter(|s| s.len() <= 256)
            .ok_or("Invalid session ID")?
            .to_owned();
        let preview = match payload["preferences"].get("previewText") {
            None | Some(Value::Null) => DEFAULT_PREVIEW,
            Some(v) => v.as_str().ok_or("Preview Text must be a string")?,
        };
        preview::bounded(preview)?;
        let query = payload["searchText"].as_str().unwrap_or("");
        if query.len() > MAX_QUERY {
            return Err("Search text exceeds 4096 UTF-8 bytes".into());
        }
        let prefs = store::preferences(&ctx.paths.data_dir)?;
        let token = self.serial();
        let owner = ctx.clone();
        let value = Arc::new(AsyncMutex::new(Session {
            token,
            revision: 0,
            draft_revision: 0,
            query: query.into(),
            font_query: query.into(),
            filter: prefs.filter,
            preview: preview.into(),
            names: None,
            limit: PAGE,
            actions: HashMap::new(),
            pending: None,
            message: None,
        }));
        let mut map = self.registry.lock().map_err(|e| e.to_string())?;
        prune(&mut map);
        if map.len() >= MAX_SESSIONS || map.contains_key(&id) {
            return Err("Font Search session capacity reached".into());
        }
        map.insert(
            id.clone(),
            Entry {
                token,
                cancel: Box::pin(async move { owner.cancelled().await }),
                value: value.clone(),
            },
        );
        Ok((
            value,
            OpenGuard {
                registry: self.registry.clone(),
                id,
                token,
                armed: true,
            },
        ))
    }
    fn current(&self, payload: &Value, state: &Value) -> Result<Arc<AsyncMutex<Session>>, String> {
        let mut map = self.registry.lock().map_err(|e| e.to_string())?;
        prune(&mut map);
        let id = payload["sessionId"].as_str().ok_or("Missing session ID")?;
        map.get(id)
            .filter(|e| Some(e.token) == state["owner"].as_u64())
            .map(|e| e.value.clone())
            .ok_or("Session is no longer owned by Font Search".into())
    }
    fn action(
        &self,
        session: &mut Session,
        actions: &mut Vec<Value>,
        title: &str,
        kind: &str,
        value: Action,
    ) -> String {
        let id = format!(
            "font:{}:{}:{}",
            session.token,
            session.revision,
            self.serial()
        );
        session.actions.insert(id.clone(), value);
        let mut wire = json!({"id":id,"title":title,"kind":kind});
        if title == "Show PostScript Names" {
            wire["shortcut"] = json!({"modifiers":["cmd"],"key":"n"});
        }
        if title == "Pin Font" || title == "Unpin Font" {
            wire["shortcut"] = json!({"modifiers":["cmd","shift"],"key":"p"});
        }
        actions.push(wire);
        id
    }
    fn render(&self, s: &mut Session, fonts: &[Font], prefs: &store::Preferences) -> CoreResult {
        s.revision += 1;
        s.actions.clear();
        let mut actions = Vec::new();
        let mut sections = Vec::new();
        let filter_id = format!("font:{}:filter", s.token);
        let title;
        let mut props = json!({"searchText":s.query,"__hasServerSearch":true,"filtering":false,"draftRevision":s.draft_revision,"inputDraft":{"revision":s.draft_revision,"searchText":s.query,"filter":s.filter,"previewText":s.preview}});
        if let Some(font) = s.names.clone() {
            title = format!("PostScript Names for {}", font.name);
            props["navigationTitle"] = json!(title);
            props["searchBarPlaceholder"] = json!("Search PostScript names...");
            let back = self.action(s, &mut actions, "Back", "pop", Action::Back);
            props["backActionId"] = json!(back);
            let query = s.query.to_lowercase();
            for name in font
                .post_script_names
                .iter()
                .filter(|n| n.to_lowercase().contains(&query))
            {
                let ids = if s.pending.is_none() {
                    vec![self.action(
                        s,
                        &mut actions,
                        "Copy PostScript Name",
                        "copy",
                        Action::Copy(name.clone(), "PostScript name copied"),
                    )]
                } else {
                    Vec::new()
                };
                sections.push(
                    json!({"type":"List.Item","props":{"id":name,"title":name,"actionIds":ids}}),
                );
            }
            if sections.is_empty() {
                sections.push(json!({"type":"List.EmptyView","props":{"title":if font.post_script_names.is_empty(){"No PostScript Names"}else{"No matching PostScript names"},"description":if font.post_script_names.is_empty(){format!("No PostScript names found for {}.",font.name)}else{"Try a different search term.".into()}}}));
            }
        } else {
            title = "Search Fonts".into();
            props["searchBarPlaceholder"] = json!("Search fonts...");
            props["isShowingDetail"] = json!(true);
            props["searchBarAccessory"] = json!({"type":"List.Dropdown","props":{"tooltip":"Filter System Fonts","storeValue":true,"value":s.filter,"actionId":filter_id},"children":[{"type":"List.Dropdown.Item","props":{"title":"All Fonts","value":"all"}},{"type":"List.Dropdown.Item","props":{"title":"User Fonts Only","value":"user"}}]});
            let query = s.query.to_lowercase();
            let filtered: Vec<_> = fonts
                .iter()
                .filter(|f| {
                    f.name.to_lowercase().contains(&query) && (s.filter == "all" || !f.is_system)
                })
                .collect();
            let pinned: Vec<_> = filtered
                .iter()
                .copied()
                .filter(|f| prefs.pinned_fonts.contains(&f.name))
                .collect();
            let unpinned: Vec<_> = filtered
                .iter()
                .copied()
                .filter(|f| !prefs.pinned_fonts.contains(&f.name))
                .collect();
            let mut remaining = s.limit;
            for (section, list) in [
                ("Pinned", &pinned),
                (if pinned.is_empty() { "All" } else { "Other" }, &unpinned),
            ] {
                if section == "Pinned" && list.is_empty() {
                    continue;
                }
                let mut rows = Vec::new();
                for font in list.iter().take(remaining) {
                    let is_pinned = prefs.pinned_fonts.contains(&font.name);
                    let mut ids = Vec::new();
                    if s.pending.is_none() {
                        ids.push(self.action(
                            s,
                            &mut actions,
                            "Copy Font Name",
                            "copy",
                            Action::Copy(font.name.clone(), "Font name copied"),
                        ));
                        ids.push(self.action(
                            s,
                            &mut actions,
                            "Show in Finder",
                            "show-in-finder",
                            Action::Reveal(font.path.clone()),
                        ));
                    }
                    ids.push(self.action(
                        s,
                        &mut actions,
                        "Show PostScript Names",
                        "push",
                        Action::Names((*font).clone()),
                    ));
                    ids.push(self.action(
                        s,
                        &mut actions,
                        if is_pinned { "Unpin Font" } else { "Pin Font" },
                        "action",
                        Action::Pin(font.name.clone()),
                    ));
                    ids.push(self.action(
                        s,
                        &mut actions,
                        "Reload Font List",
                        "action",
                        Action::Reload,
                    ));
                    let metadata=vec![("Type",if font.is_system{"System Font"}else{"User Font"}.to_owned()),("Path",font.path.clone()),("Styles","Regular".into()),("Pinned",if is_pinned{"Yes"}else{"No"}.into())].into_iter().map(|(title,text)|json!({"type":"List.Item.Detail.Metadata.Label","props":{"title":title,"text":text}})).collect::<Vec<_>>();
                    rows.push(json!({"type":"List.Item","props":{"id":format!("{}-{}{}",font.name,font.path,if is_pinned{"-pinned"}else{""}),"title":font.name,"icon":if is_pinned{"Icon.Tack"}else if font.is_system{"Icon.Text"}else{"Icon.QuotationMarks"},"actionIds":ids},"children":[{"type":"List.Item.Detail","props":{"markdown":preview::markdown(&font.name,&s.preview).unwrap_or_else(|error| format!("Preview unavailable: {error}"))},"metadata":{"type":"List.Item.Detail.Metadata","children":metadata}}]}));
                }
                remaining = remaining.saturating_sub(rows.len());
                sections
                    .push(json!({"type":"List.Section","props":{"title":section},"children":rows}));
            }
            props["__hasMore"] = json!(filtered.len() > s.limit && s.limit < MAX_VISIBLE);
            if filtered.len() > s.limit && s.limit == MAX_VISIBLE {
                s.message = Some(format!("Showing {MAX_VISIBLE} of {} matching fonts. Narrow the search to view the remaining fonts; the full catalog is searchable.", filtered.len()));
            }
            props["fontCount"] = json!(filtered.len());
            if filtered.is_empty() {
                sections.push(json!({"type":"List.EmptyView","props":{"title":"No matching fonts","description":"Try a different search term or font filter."}}));
            }
            if fonts.is_empty() {
                self.action(
                    s,
                    &mut actions,
                    "Reload Font List",
                    "action",
                    Action::Reload,
                );
            }
        }
        if s.pending.is_some() {
            self.action(
                s,
                &mut actions,
                "Retry Frozen Action (may duplicate)",
                "action",
                Action::Retry,
            );
            self.action(
                s,
                &mut actions,
                "Dismiss Unknown Result",
                "action",
                Action::Dismiss,
            );
        }
        let mut result = tezbar_extension_sdk::view(
            &title,
            json!({"type":"List","props":props,"children":sections}),
            actions,
        );
        result["refreshMs"] = Value::Null;
        if let Some(message) = &s.message {
            result["message"] = json!(message);
        }
        if s.pending.is_some() {
            result["message"]=json!("Action outcome is unknown. A retry uses the exact original text/path and may duplicate an action that already completed.");
        }
        if serde_json::to_vec(&result)
            .map_err(|e| e.to_string())?
            .len()
            > MAX_VIEW
        {
            return Err("Font view exceeds 12 MiB; narrow search or reduce Preview Text (no partial view emitted)".into());
        }
        Ok(result)
    }
    /// Capture ownership BEFORE validation so an invalid intermediate edit still
    /// fences older A/B/A responses. Complete drafts are optional for old hosts.
    fn draft(s: &mut Session, draft: &Value) -> Result<bool, String> {
        if draft.is_null() {
            return Ok(false);
        }
        let revision = draft["revision"].as_u64().ok_or("Invalid draft revision")?;
        if revision > 9_007_199_254_740_991 {
            return Err("Draft revision exceeds JavaScript safe integer limit".into());
        }
        if revision <= s.draft_revision {
            return Ok(false);
        }
        s.draft_revision = revision;
        s.actions.clear();
        s.limit = PAGE;
        let query = draft["searchText"].as_str().ok_or("Invalid search draft")?;
        if query.len() > MAX_QUERY {
            return Err("Search text exceeds 4096 UTF-8 bytes".into());
        }
        s.query = query.into();
        if s.names.is_none() {
            s.font_query = s.query.clone();
            let filter = draft["filter"]
                .as_str()
                .ok_or("Missing complete filter draft")?;
            if !["all", "user"].contains(&filter) {
                return Err("Invalid font filter".into());
            }
            s.filter = filter.into();
        }
        Ok(true)
    }
    async fn operate(
        &self,
        ctx: &ExtensionContext,
        op: &str,
        p: &Value,
        state: &mut Value,
    ) -> CoreResult {
        if op == "extension:dispose-session" {
            if let Some(id) = p["sessionId"].as_str() {
                self.registry.lock().map_err(|e| e.to_string())?.remove(id);
            }
            return Ok(tezbar_extension_sdk::unchanged());
        }
        let (value, mut guard) = if op == "extension:run-command" {
            let (v, g) = self.register(ctx, p)?;
            (v, Some(g))
        } else {
            (self.current(p, state)?, None)
        };
        let mut s = value.lock().await;
        s.message = None;
        let mut fonts = match self.catalog(ctx, false).await {
            Ok(f) => f,
            Err(e) => {
                s.message = Some(format!("Error fetching fonts: {e}"));
                Arc::new(Vec::new())
            }
        };
        let _persistence = self.persistence.lock().await;
        let mut prefs = store::preferences(&ctx.paths.data_dir)?;
        match op {
            "extension:run-command" => {}
            "extension:refresh-session" => {}
            "extension:load-more" => {
                s.limit = (s.limit + PAGE).min(MAX_VISIBLE);
            }
            "extension:search-text-changed" => {
                if p["__draft"]["revision"]
                    .as_u64()
                    .is_some_and(|r| r < s.draft_revision)
                {
                    return Ok(tezbar_extension_sdk::unchanged());
                }
                if !p["__draft"].is_null() {
                    if let Err(e) = Self::draft(&mut s, &p["__draft"]) {
                        s.message = Some(e);
                    }
                } else {
                    let q = p["searchText"].as_str().ok_or("Missing search text")?;
                    s.draft_revision = s
                        .draft_revision
                        .checked_add(1)
                        .ok_or("Input revision exhausted; reopen Font Search")?;
                    s.actions.clear();
                    if q.len() > MAX_QUERY {
                        s.message = Some("Search text exceeds 4096 UTF-8 bytes".into())
                    } else {
                        s.query = q.into();
                        if s.names.is_none() {
                            s.font_query = q.into();
                        }
                        s.limit = PAGE;
                    }
                }
            }
            "extension:invoke-action" => {
                let id = p["actionId"].as_str().ok_or("Missing action ID")?;
                let filter_id = format!("font:{}:filter", s.token);
                let old_revision = s.draft_revision;
                if p["formValues"]["__draft"]["revision"]
                    .as_u64()
                    .is_some_and(|r| r < s.draft_revision)
                {
                    return Ok(tezbar_extension_sdk::unchanged());
                }
                if !p["formValues"]["__draft"].is_null() {
                    if let Err(e) = Self::draft(&mut s, &p["formValues"]["__draft"]) {
                        s.message = Some(e);
                        return self.render(&mut s, &fonts, &prefs);
                    }
                }
                if id == filter_id && s.names.is_none() {
                    let filter = p["formValues"]["value"]
                        .as_str()
                        .ok_or("Missing font filter")?;
                    if !["all", "user"].contains(&filter) {
                        s.draft_revision = s
                            .draft_revision
                            .checked_add(1)
                            .ok_or("Input revision exhausted; reopen Font Search")?;
                        s.actions.clear();
                        s.message = Some("Invalid font filter".into());
                    } else {
                        s.filter = filter.into();
                        prefs.filter = filter.into();
                        store::save_preferences(&ctx.paths.data_dir, &prefs)?;
                        s.limit = PAGE;
                    }
                } else if s.draft_revision != old_revision { /* unsent draft invalidates old row actions */
                } else if let Some(action) = s.actions.remove(id) {
                    // Runtime ledger is outside SDK staged state. Consume before
                    // any await: cancellation/error cannot roll an action ID back.
                    let effect = match action {
                        Action::Copy(text, title) => Some(Effect {
                            method: "host.clipboard.write",
                            params: json!({"text":text}),
                            title,
                        }),
                        Action::Reveal(path) => Some(Effect {
                            method: "host.shell.reveal",
                            params: json!({"path":path}),
                            title: "",
                        }),
                        Action::Retry => s.pending.clone(),
                        Action::Dismiss => {
                            s.pending = None;
                            None
                        }
                        Action::Names(font) => {
                            s.names = Some(font);
                            s.query = String::new();
                            s.limit = PAGE;
                            None
                        }
                        Action::Back => {
                            s.names = None;
                            s.query = s.font_query.clone();
                            s.limit = PAGE;
                            None
                        }
                        Action::Pin(name) => {
                            if prefs.pinned_fonts.contains(&name) {
                                prefs.pinned_fonts.retain(|n| n != &name);
                            } else {
                                prefs.pinned_fonts.push(name);
                            }
                            store::save_preferences(&ctx.paths.data_dir, &prefs)?;
                            None
                        }
                        Action::Reload => {
                            match self.catalog(ctx, true).await {
                                Ok(f) => fonts = f,
                                Err(e) => {
                                    s.message = Some(format!("Error fetching fonts: {e}"));
                                    fonts = Arc::new(Vec::new());
                                }
                            }
                            None
                        }
                    };
                    if let Some(effect) = effect {
                        s.actions.clear();
                        s.pending = Some(effect.clone());
                        let result = ctx.host(effect.method, effect.params).await;
                        match result.and_then(ack) {
                            Ok(()) => {
                                s.pending = None;
                                if !effect.title.is_empty() {
                                    s.message = Some(effect.title.into());
                                }
                            }
                            Err(error) => {
                                s.message = Some(format!(
                                    "Action outcome unknown: {error}. Retry may duplicate."
                                ));
                            }
                        }
                    }
                } else {
                    return Ok(tezbar_extension_sdk::unchanged());
                }
            }
            _ => return Err(format!("Unsupported Font Search operation: {op}")),
        }
        let result = self.render(&mut s, &fonts, &prefs)?;
        *state = json!({"owner":s.token});
        if let Some(g) = guard.as_mut() {
            g.armed = false;
        }
        Ok(result)
    }
}
/// Closed acknowledgement contract, including optional message's exact type.
fn ack(value: Value) -> Result<(), String> {
    let obj = value
        .as_object()
        .ok_or("Host acknowledgement must be {ok:true,message?:string}")?;
    if obj.get("ok") != Some(&json!(true))
        || obj.keys().any(|k| k != "ok" && k != "message")
        || obj.get("message").is_some_and(|v| !v.is_string())
    {
        return Err("Host rejected or malformed acknowledgement".into());
    }
    Ok(())
}
impl Extension for Adapter {
    fn id(&self) -> &'static str {
        ID
    }
    fn version(&self) -> &'static str {
        VERSION
    }
    fn commands(&self) -> &'static [&'static str] {
        &["search-fonts"]
    }
    fn handle<'a>(
        &'a self,
        ctx: &'a ExtensionContext,
        command: &'a str,
        operation: &'a str,
        payload: &'a Value,
        state: &'a mut Value,
    ) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            if command != "search-fonts" {
                return Err("Unknown Font Search command".into());
            }
            self.operate(ctx, operation, payload, state).await
        })
    }
    fn shutdown<'a>(&'a self, _ctx: &'a ExtensionContext) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            self.registry.lock().map_err(|e| e.to_string())?.clear();
            *self.catalog.lock().await = None;
            Ok(json!({}))
        })
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn closed_ack() {
        for v in [
            json!(null),
            json!(true),
            json!(false),
            json!({}),
            json!({"ok":false}),
            json!({"ok":true,"error":"no"}),
            json!({"ok":true,"message":42}),
            json!({"ok":true,"success":false}),
        ] {
            assert!(ack(v).is_err());
        }
        for v in [json!({"ok":true}), json!({"ok":true,"message":"Copied"})] {
            assert!(ack(v).is_ok());
        }
    }
}
