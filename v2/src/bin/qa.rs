//! Owned-fixture runner only. Never packaged. No production environment override.
use std::{
    path::{Path, PathBuf},
    sync::Arc,
};
use tezbar_extension_sdk::BoxFuture;
use tezbar_font_search::{
    discovery::{self, Font, Provider, Root},
    Adapter,
};
struct Owned {
    roots: Vec<Root>,
    delay: u64,
}
impl Provider for Owned {
    fn discover<'a>(&'a self, platform: &'a str) -> BoxFuture<'a, Result<Vec<Font>, String>> {
        Box::pin(async move {
            if self.delay > 0 {
                eprintln!("qa:discovery-start");
                tokio::time::sleep(std::time::Duration::from_millis(self.delay)).await;
            }
            let roots: Vec<_> = self
                .roots
                .iter()
                .filter(|r| platform != "Windows" || !r.path.ends_with("system-b"))
                .cloned()
                .collect();
            discovery::scan(&roots, "en-US").await
        })
    }
}
fn owned(path: &Path) -> Result<PathBuf, String> {
    let scope = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join(".qa")
        .canonicalize()
        .map_err(|e| e.to_string())?;
    let path = path.canonicalize().map_err(|e| e.to_string())?;
    if !path.starts_with(&scope) || path == scope {
        return Err("QA input must be inside this v2/.qa".into());
    }
    Ok(path)
}
#[tokio::main(worker_threads = 2)]
async fn main() {
    if let Err(e) = run().await {
        eprintln!("font-search-qa: {e}");
        std::process::exit(1)
    }
}
async fn run() -> Result<(), String> {
    let args: Vec<_> = std::env::args().collect();
    let root = owned(Path::new(args.get(1).ok_or("Owned fixture root required")?))?;
    if args.get(2).is_some_and(|s| s == "--svg") {
        println!(
            "{}",
            tezbar_font_search::preview::svg(
                args.get(3).ok_or("Font family required")?,
                args.get(4).ok_or("Preview text required")?
            )?
        );
        return Ok(());
    }
    if args.get(2).is_some_and(|s| s == "--render") {
        use std::io::Read;
        let svg_path = owned(Path::new(args.get(3).ok_or("Owned SVG required")?))?;
        let output = Path::new(args.get(4).ok_or("Owned PNG path required")?);
        owned(output.parent().ok_or("Owned PNG parent required")?)?;
        let mut font = Vec::new();
        std::fs::File::open(&root)
            .map_err(|e| e.to_string())?
            .take(1024 * 1024 + 1)
            .read_to_end(&mut font)
            .map_err(|e| e.to_string())?;
        if font.len() > 1024 * 1024 {
            return Err("Owned font exceeds 1 MiB".into());
        }
        let mut svg = Vec::new();
        std::fs::File::open(svg_path)
            .map_err(|e| e.to_string())?
            .take(65537)
            .read_to_end(&mut svg)
            .map_err(|e| e.to_string())?;
        if svg.len() > 65536 {
            return Err("Owned SVG exceeds 64 KiB".into());
        }
        let mut options = resvg::usvg::Options {
            font_family: "QA Specimen".into(),
            ..Default::default()
        };
        // Database::new is empty. NEVER load_system_fonts/load_fonts_dir.
        let db = options.fontdb_mut();
        db.load_font_data(font);
        db.set_serif_family("QA Specimen");
        db.set_sans_serif_family("QA Specimen");
        db.set_monospace_family("QA Specimen");
        let tree = resvg::usvg::Tree::from_data(&svg, &options).map_err(|e| e.to_string())?;
        if tree.size().width() != 600.0 || tree.size().height() != 300.0 {
            return Err("Expected original 600x300 specimen".into());
        }
        let mut pixmap =
            resvg::tiny_skia::Pixmap::new(600, 300).ok_or("Pixmap allocation failed")?;
        resvg::render(
            &tree,
            resvg::tiny_skia::Transform::identity(),
            &mut pixmap.as_mut(),
        );
        let occupied = pixmap.pixels().iter().filter(|p| p.alpha() > 0).count();
        if occupied == 0 {
            return Err("Font specimen rendered no outlines".into());
        }
        pixmap.save_png(output).map_err(|e| e.to_string())?;
        println!(
            "{}",
            serde_json::json!({"occupiedPixels":occupied,"width":600,"height":300,"fonts":tree.fontdb().faces().count(),"systemFontsLoaded":false})
        );
        return Ok(());
    }
    if args.get(2).is_some_and(|s| s == "--parse") {
        let bytes = std::fs::read(&root).map_err(|e| e.to_string())?;
        if bytes.len() > 1024 * 1024 {
            return Err("QA font fixture exceeds 1 MiB".into());
        }
        let count = ttf_parser::fonts_in_collection(&bytes).unwrap_or(1);
        for index in 0..count {
            let face = ttf_parser::Face::parse(&bytes, index).map_err(|e| format!("{e:?}"))?;
            println!(
                "{}",
                serde_json::json!({"face":index,"glyphs":face.number_of_glyphs(),"unitsPerEm":face.units_per_em(),"hasA":face.glyph_index('A').is_some()})
            );
        }
        return Ok(());
    }
    let roots = vec![
        Root {
            path: root.join("system-a"),
            system: true,
        },
        Root {
            path: root.join("system-b"),
            system: true,
        },
        Root {
            path: root.join("user"),
            system: false,
        },
    ];
    let delay = if args.get(2).is_some_and(|s| s == "--slow") {
        500
    } else {
        0
    };
    let windows = args.get(2).is_some_and(|s| s == "--catalog-windows");
    let roots: Vec<_> = roots
        .into_iter()
        .filter(|r| !windows || !r.path.ends_with("system-b"))
        .collect();
    if args
        .get(2)
        .is_some_and(|s| s == "--catalog" || s == "--catalog-windows")
    {
        println!(
            "{}",
            serde_json::to_string(&discovery::scan(&roots, "en-US").await?)
                .map_err(|e| e.to_string())?
        );
        return Ok(());
    }
    tezbar_extension_sdk::serve(Adapter::with_fixture_provider(Arc::new(Owned {
        roots,
        delay,
    })))
    .await
}
