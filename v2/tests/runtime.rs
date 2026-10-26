#![cfg(feature = "qa")]
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc,
};
use tezbar_extension_sdk::{BoxFuture, Extension, ExtensionPaths, TestContext};
use tezbar_font_search::{
    discovery::{Font, Provider},
    Adapter,
};
struct Fixture(Arc<AtomicUsize>);
impl Provider for Fixture {
    fn discover<'a>(&'a self, _: &'a str) -> BoxFuture<'a, Result<Vec<Font>, String>> {
        Box::pin(async {
            self.0.fetch_add(1, Ordering::SeqCst);
            Ok(vec![Font {
                name: "Owned Font".into(),
                path: std::env::temp_dir()
                    .join("owned-fonts/Owned-Font.ttf")
                    .to_string_lossy()
                    .into_owned(),
                is_system: false,
                styles: vec!["Regular".into()],
                post_script_names: vec!["Owned Font".into()],
            }])
        })
    }
}
fn context() -> (tempfile::TempDir, TestContext) {
    let t = tempfile::tempdir().unwrap();
    let ctx = TestContext::new(
        ExtensionPaths {
            data_dir: t.path().join("data"),
            temp_dir: t.path().join("temp"),
            package_dir: t.path().join("package"),
        },
        &["clipboard.write", "shell.reveal"],
    );
    (t, ctx)
}
async fn call(a: &Adapter, c: &TestContext, op: &str, p: Value, state: &mut Value) -> Value {
    c.run(a.handle(&c.context, "search-fonts", op, &p, state))
        .await
        .unwrap()
}
fn id(v: &Value, title: &str) -> String {
    v["actions"]
        .as_array()
        .unwrap()
        .iter()
        .find(|a| a["title"] == title)
        .unwrap()["id"]
        .as_str()
        .unwrap()
        .into()
}
#[tokio::test]
async fn copy_ack_repeats_and_stale_cross_session_actions_are_inert() {
    let (_t, c) = context();
    let count = Arc::new(AtomicUsize::new(0));
    let a = Adapter::with_fixture_provider(Arc::new(Fixture(count.clone())));
    let mut state = json!({});
    let v = call(
        &a,
        &c,
        "extension:run-command",
        json!({"sessionId":"a","preferences":{}}),
        &mut state,
    )
    .await;
    let copy = id(&v, "Copy Font Name");
    c.reply(Ok(json!({"ok":true})));
    let v = call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"a","actionId":copy}),
        &mut state,
    )
    .await;
    assert_eq!(v["message"], "Font name copied");
    assert_ne!(id(&v, "Copy Font Name"), copy);
    assert_eq!(c.calls().len(), 1);
    let stale = call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"a","actionId":copy}),
        &mut state,
    )
    .await;
    assert_eq!(stale["mode"], "unchanged");
    assert_eq!(c.calls().len(), 1);
    c.reply(Ok(json!({"ok":true,"message":"ok"})));
    let second = id(&v, "Copy Font Name");
    call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"a","actionId":second}),
        &mut state,
    )
    .await;
    assert_eq!(c.calls().len(), 2);
    let mut other = json!({});
    call(
        &a,
        &c,
        "extension:run-command",
        json!({"sessionId":"b","preferences":{}}),
        &mut other,
    )
    .await;
    call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"b","actionId":second}),
        &mut other,
    )
    .await;
    assert_eq!(c.calls().len(), 2);
    assert_eq!(count.load(Ordering::SeqCst), 1);
}
#[tokio::test]
async fn unknown_retry_freezes_bytes_across_navigation_and_search() {
    let (_t, c) = context();
    let a = Adapter::with_fixture_provider(Arc::new(Fixture(Arc::default())));
    let mut state = json!({});
    let v = call(
        &a,
        &c,
        "extension:run-command",
        json!({"sessionId":"s","preferences":{}}),
        &mut state,
    )
    .await;
    c.reply(Ok(json!(true)));
    let v = call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"s","actionId":id(&v,"Copy Font Name")}),
        &mut state,
    )
    .await;
    assert!(v["message"].as_str().unwrap().contains("may duplicate"));
    assert!(!v["message"].as_str().unwrap().contains("Font name copied"));
    let v = call(
        &a,
        &c,
        "extension:search-text-changed",
        json!({"sessionId":"s","searchText":"nothing"}),
        &mut state,
    )
    .await;
    c.reply(Ok(json!({"ok":true})));
    call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"s","actionId":id(&v,"Retry Frozen Action (may duplicate)")}),
        &mut state,
    )
    .await;
    let calls = c.calls();
    assert_eq!(calls.len(), 2);
    assert_eq!(calls[0]["params"], calls[1]["params"]);
    assert_eq!(calls[1]["params"]["text"], "Owned Font");
}
#[tokio::test]
async fn complete_drafts_fence_a_b_a_and_invalid_intermediates() {
    let (_t, c) = context();
    let a = Adapter::with_fixture_provider(Arc::new(Fixture(Arc::default())));
    let mut state = json!({});
    let v = call(
        &a,
        &c,
        "extension:run-command",
        json!({"sessionId":"s","preferences":{}}),
        &mut state,
    )
    .await;
    let stale = id(&v, "Copy Font Name");
    for (revision, q, filter) in [
        (1, "A", "all"),
        (2, "B", "all"),
        (3, "A", "user"),
        (4, "A", "invalid"),
    ] {
        call(&a,&c,"extension:search-text-changed",json!({"sessionId":"s","searchText":q,"__draft":{"revision":revision,"searchText":q,"filter":filter}}),&mut state).await;
    }
    let late=call(&a,&c,"extension:search-text-changed",json!({"sessionId":"s","searchText":"B","__draft":{"revision":2,"searchText":"B","filter":"all"}}),&mut state).await;
    assert_eq!(late["mode"], "unchanged");
    call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"s","actionId":stale}),
        &mut state,
    )
    .await;
    assert!(c.calls().is_empty());
    let v = call(
        &a,
        &c,
        "extension:refresh-session",
        json!({"sessionId":"s"}),
        &mut state,
    )
    .await;
    assert_eq!(v["root"]["props"]["draftRevision"], 4);
    assert_eq!(v["root"]["props"]["searchText"], "A");
    assert_eq!(
        v["root"]["props"]["searchBarAccessory"]["props"]["value"],
        "user"
    );
}
#[tokio::test]
async fn persistence_pin_filter_names_reload_and_no_effect_field_changes() {
    let (t, c) = context();
    let count = Arc::new(AtomicUsize::new(0));
    let a = Adapter::with_fixture_provider(Arc::new(Fixture(count.clone())));
    let mut state = json!({});
    let v = call(
        &a,
        &c,
        "extension:run-command",
        json!({"sessionId":"s","preferences":{"previewText":"Owned preview"}}),
        &mut state,
    )
    .await;
    let v = call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"s","actionId":id(&v,"Pin Font")}),
        &mut state,
    )
    .await;
    assert_eq!(v["root"]["children"][0]["props"]["title"], "Pinned");
    assert!(c.calls().is_empty());
    let prefs: Value = serde_json::from_slice(
        &std::fs::read(t.path().join("data/font-search/storage.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(prefs["pinnedFonts"], json!(["Owned Font"]));
    let v = call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"s","actionId":id(&v,"Show PostScript Names")}),
        &mut state,
    )
    .await;
    assert_eq!(v["title"], "PostScript Names for Owned Font");
    assert!(v["actions"]
        .as_array()
        .unwrap()
        .iter()
        .any(|a| a["title"] == "Copy PostScript Name"));
    let v = call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"s","actionId":id(&v,"Back")}),
        &mut state,
    )
    .await;
    let filter = v["root"]["props"]["searchBarAccessory"]["props"]["actionId"].clone();
    let v = call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"s","actionId":filter,"formValues":{"value":"user"}}),
        &mut state,
    )
    .await;
    call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"s","actionId":id(&v,"Reload Font List")}),
        &mut state,
    )
    .await;
    assert_eq!(count.load(Ordering::SeqCst), 2);
    assert!(c.calls().is_empty());
}

struct Failure(Arc<AtomicUsize>);
impl Provider for Failure {
    fn discover<'a>(&'a self, _: &'a str) -> BoxFuture<'a, Result<Vec<Font>, String>> {
        Box::pin(async {
            self.0.fetch_add(1, Ordering::SeqCst);
            Err("owned discovery failure".into())
        })
    }
}
#[tokio::test]
async fn failures_wait_for_deliberate_reload_and_do_not_fake_empty_success() {
    let (_t, c) = context();
    let count = Arc::new(AtomicUsize::new(0));
    let a = Adapter::with_fixture_provider(Arc::new(Failure(count.clone())));
    let mut state = json!({});
    let mut v = call(
        &a,
        &c,
        "extension:run-command",
        json!({"sessionId":"s","preferences":{}}),
        &mut state,
    )
    .await;
    assert!(v["message"]
        .as_str()
        .unwrap()
        .contains("owned discovery failure"));
    for _ in 0..3 {
        v = call(
            &a,
            &c,
            "extension:refresh-session",
            json!({"sessionId":"s"}),
            &mut state,
        )
        .await;
    }
    assert_eq!(count.load(Ordering::SeqCst), 1);
    call(
        &a,
        &c,
        "extension:invoke-action",
        json!({"sessionId":"s","actionId":id(&v,"Reload Font List")}),
        &mut state,
    )
    .await;
    assert_eq!(count.load(Ordering::SeqCst), 2);
    assert!(c.calls().is_empty());
}
struct Many;
impl Provider for Many {
    fn discover<'a>(&'a self, _: &'a str) -> BoxFuture<'a, Result<Vec<Font>, String>> {
        Box::pin(async {
            Ok((0..300)
                .map(|n| Font {
                    name: format!("Owned {n:03}"),
                    path: std::env::temp_dir()
                        .join(format!("owned-fonts/{n}.ttf"))
                        .to_string_lossy()
                        .into_owned(),
                    is_system: false,
                    styles: vec!["Regular".into()],
                    post_script_names: vec![format!("Owned {n:03}")],
                })
                .collect())
        })
    }
}
#[tokio::test]
async fn complete_catalog_stays_searchable_beyond_explicit_view_bound() {
    let (_t, c) = context();
    let a = Adapter::with_fixture_provider(Arc::new(Many));
    let mut state = json!({});
    let mut v = call(
        &a,
        &c,
        "extension:run-command",
        json!({"sessionId":"s","preferences":{}}),
        &mut state,
    )
    .await;
    assert_eq!(v["root"]["props"]["fontCount"], 300);
    for _ in 0..8 {
        v = call(
            &a,
            &c,
            "extension:load-more",
            json!({"sessionId":"s"}),
            &mut state,
        )
        .await;
    }
    assert_eq!(v["root"]["props"]["__hasMore"], false);
    assert!(v["message"].as_str().unwrap().contains("256 of 300"));
    v = call(
        &a,
        &c,
        "extension:search-text-changed",
        json!({"sessionId":"s","searchText":"299"}),
        &mut state,
    )
    .await;
    assert_eq!(v["root"]["props"]["fontCount"], 1);
    assert_eq!(
        v["root"]["children"][0]["children"][0]["props"]["title"],
        "Owned 299"
    );
}
