pub mod discovery;
pub mod preview;
mod runtime;
mod store;
pub use runtime::Adapter;
pub const ID: &str = "com.tezbar.native.font-search";
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
pub const DEFAULT_PREVIEW: &str = "Sphinx of black quartz, judge my vow.";
