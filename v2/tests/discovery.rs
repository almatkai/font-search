use std::path::Path;
use tezbar_font_search::{discovery::*, preview};
#[test]
fn filename_contract() {
    let f = from_path(Path::new("/owned/A---__B.TTF"), true)
        .unwrap()
        .unwrap();
    assert_eq!(f.name, "A B");
    assert_eq!(f.styles, ["Regular"]);
    assert_eq!(f.post_script_names, ["A B"]);
    assert!(f.is_system);
    assert!(from_path(Path::new("/owned/.ttf"), false)
        .unwrap()
        .is_none());
    assert!(from_path(Path::new("/owned/font.svg"), false)
        .unwrap()
        .is_none());
    assert_eq!(
        from_path(Path::new("/owned/a.b.woff2"), false)
            .unwrap()
            .unwrap()
            .name,
        "a.b"
    );
}
#[test]
fn exact_root_scope() {
    let r = roots("darwin", Path::new("/owned/home"), None, None).unwrap();
    assert_eq!(
        r.iter().map(|r| r.path.clone()).collect::<Vec<_>>(),
        [
            Path::new("/System/Library/Fonts").to_path_buf(),
            Path::new("/Library/Fonts").to_path_buf(),
            Path::new("/owned/home/Library/Fonts").to_path_buf()
        ]
    );
    assert_eq!(
        r.iter().map(|r| r.system).collect::<Vec<_>>(),
        [true, true, false]
    );
    let r = roots(
        "win32",
        Path::new("/owned/home"),
        Some("/owned/Windows"),
        Some("/owned/Local"),
    )
    .unwrap();
    assert_eq!(r[0].path, Path::new("/owned/Windows/Fonts"));
    assert_eq!(r[1].path, Path::new("/owned/Local/Microsoft/Windows/Fonts"));
    assert!(!r[1].system);
    assert!(roots("linux", Path::new("/owned"), None, None).is_err());
}
#[tokio::test]
async fn owned_scan_dedup_stack_hidden_and_malformed() {
    let t = tempfile::tempdir().unwrap();
    let a = t.path().join("system");
    let b = t.path().join("user");
    std::fs::create_dir_all(a.join("a")).unwrap();
    std::fs::create_dir_all(a.join("z")).unwrap();
    std::fs::create_dir_all(&b).unwrap();
    for path in [
        a.join("Same.ttf"),
        b.join("Same.ttf"),
        a.join(".Hidden.ttf"),
        b.join("a-b.otf"),
        a.join("a/Sub.ttf"),
        a.join("z/Sub.ttf"),
    ] {
        std::fs::write(path, b"malformed, but V1 reads names only").unwrap();
    }
    let f = scan(
        &[
            Root {
                path: a.clone(),
                system: true,
            },
            Root {
                path: b,
                system: false,
            },
            Root {
                path: t.path().join("missing"),
                system: false,
            },
        ],
        "en-US",
    )
    .await
    .unwrap();
    assert_eq!(
        f.iter().map(|f| f.name.as_str()).collect::<Vec<_>>(),
        ["a b", "Same", "Sub"]
    );
    assert!(f[1].is_system);
    assert!(Path::new(&f[2].path).ends_with("z/Sub.ttf"));
    assert_eq!(f[2].styles, ["Regular"]);
}
#[cfg(unix)]
#[tokio::test]
async fn non_utf8_is_explicit_error() {
    use std::os::unix::ffi::OsStringExt;
    let path = std::path::PathBuf::from(std::ffi::OsString::from_vec(vec![
        b'/', 255, b'.', b't', b't', b'f',
    ]));
    assert!(from_path(&path, false).unwrap_err().contains("UTF-8"));
}
#[test]
fn bounded_preview_is_real_svg_family_lookup() {
    let s = preview::svg("A\"<&", "<hello>&").unwrap();
    assert!(s.contains("font-family=\"A&quot;&lt;&amp;\""));
    assert!(s.contains("&lt;hello&gt;&amp;"));
    assert_eq!(s.matches("<text ").count(), 4);
    assert!(s.contains("y=\"220\""));
    assert!(s.contains("600"));
    assert!(preview::svg("a", &"x".repeat(4097)).is_err());
    assert!(preview::svg("a", "\0").is_err());
    assert!(preview::svg("bad\u{1}name", "text").is_err());
}
#[test]
fn count_and_metadata_bounds_are_errors() {
    let f = from_path(Path::new("/owned/font.ttf"), false)
        .unwrap()
        .unwrap();
    let mut invalid = f.clone();
    invalid.styles = vec!["Invented Bold".into()];
    assert!(validate(&[invalid]).is_err());
    assert!(validate(&vec![f; MAX_FONTS + 1])
        .unwrap_err()
        .contains("count"));
    assert!(from_path(
        Path::new(&format!("/owned/{}.ttf", "x".repeat(MAX_NAME + 1))),
        false
    )
    .is_err());
}
