// Only copied pinned producer fragments, never the app's dirty working files.
// qa/host_contracts.py generates this from verified Git objects before tests.
#![cfg(feature = "qa")]
// Preserve the pinned producer arm verbatim, including its explicit return.
#![allow(clippy::needless_return)]
include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/.qa/generated-host-contracts.rs"
));
