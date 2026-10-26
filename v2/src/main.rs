#[tokio::main(worker_threads = 2)]
async fn main() {
    if let Err(error) = tezbar_extension_sdk::serve(tezbar_font_search::Adapter::production()).await
    {
        eprintln!("font-search: {error}");
        std::process::exit(1);
    }
}
