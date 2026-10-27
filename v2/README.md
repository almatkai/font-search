# Font Search — external Rust development port

One command, `search-fonts` (Search Fonts), for `com.tezbar.native.font-search`.
Standalone executable, schema 3, protocol 1, SDK **0.1.1**, MSRV **1.85**.
SDK dependency is immutable HTTPS Git revision
`e955911f0bf5b558f9d3eb5183df0adc95c22af2`; no sibling path dependency.
Portable V1 authority is this repository at
`f52afb19ac55199fa4ecbe2c3d94f82a831cb2ca`.

This is an **unpublished development port for review**. `artifacts` is empty and
both manifest platform verification states remain `not-run`. Automated fixtures,
cross-checking and a development archive do not establish installed-font or GUI
acceptance. There is no host registration, catalog change, installation or release
workflow in this directory.

## Source behavior

V1's own portable producer scans these roots in order:

* macOS: `/System/Library/Fonts`, `/Library/Fonts`, `~/Library/Fonts`.
* Windows: `%WINDIR%/Fonts` (default `C:\Windows`), then
  `%LOCALAPPDATA%/Microsoft/Windows/Fonts` (default `~/AppData/Local`).

Rust uses native filesystem calls, native home-directory resolution (`dirs`) and
native locale lookup (`sys-locale`); there are no Node/Bun, Swift, PowerShell or
shell enumeration helpers. It recursively visits **only those font roots**. It
never installs fonts, changes an OS cache, reads the rest of home, or enumerates
fonts through a broader registry/CoreText/DirectWrite inventory that V1 did not
use. Directory symlinks encountered below a root are not followed, matching V1
`Dirent.isDirectory`. A font-named symlink is listed by its pathname, as in V1.
Missing/protected directories are skipped. Unexpected I/O errors are explicit.

Extensions are case-insensitive `.ttf`, `.otf`, `.ttc`, `.woff`, `.woff2`.
Names are the filename stem with each `[-_]+` run replaced by one space, without
trimming. First occurrence by name wins across ordered roots, then dot-prefixed
names disappear and stable ICU collation sorts the result. Directory entry order
and the LIFO traversal are preserved. The tests compare every field and order
against the actual V1 producer for both platform branches.

V1 does **not** parse family/style/PostScript metadata. Therefore this port also
reports `styles: ["Regular"]` and `postScriptNames: [filename-derived name]`,
including for malformed files. It does not invent a richer font catalog. The
PostScript-name screen preserves that V1 behavior, its search and empty states.
ICU 1.5 uses the native locale; collation for newer Unicode or unusual locales can
differ from the Node runtime's ICU version. Locale-dependent real-machine order
has not been accepted through a GUI.

Search is case-insensitive substring matching of names. The stored All Fonts /
User Fonts Only filter, Pinned/Other/All sections, copy-name, reveal, nested-name
copy, pin/unpin and deliberate Reload actions are implemented. Pinning/search/
filter changes do not trigger discovery. The persisted installed-font catalog is
reused until Reload; process restarts reuse that same cache. A discovery failure
is retained within the process until a deliberate Reload. Initial open and Reload
await discovery; there is no detached loader, polling timer or actor. Cancellation
is cooperative between directories; a native filesystem syscall cannot be
preempted mid-call. The host process deadline is the final containment boundary.

`previewText` has the original default:
`Sphinx of black quartz, judge my vow.` Explicit empty text remains empty.
The SDK freezes declared preferences for a session; changing host preferences
requires reopening the command. No extra editable preview-text feature is added.
Pins/filter live in extension-private `font-search/storage.json`; the catalog is
`font-search/installed-fonts.json`. Unknown store keys survive writes. Writes use
a local synced tempfile and atomic replacement. Existing V1 Cache/LocalStorage
files are not imported: no source-mapped migration file contract is present in
this repository, so no broad profile read or speculative migration is declared.
The host supplies the ordinary declared preferences through the SDK.

## Actual preview contract

Each font row contains a real Markdown data-URI **SVG image**, like V1:
600×300, font size 24, x=10, baselines 70/120/170/220, with the preference text,
uppercase alphabet, lowercase alphabet and `0123456789!@#$%^()_+-={}[]:;`.
Its `font-family` is the filename-derived V1 name. The webview's installed family
lookup and fallback render the specimen. A filename can differ from a registered
family; V1 already falls back in that case. This port does not claim to render the
bytes of that particular file, choose a new style, or manufacture missing glyphs.
No font bytes are read or embedded by the production preview producer.

Invalid font-name controls show an explicit per-row preview error.
XML metacharacters are escaped instead of allowing V1's unescaped markup
interpolation; invalid XML controls are rejected. Fill is `#eeeeee` for the pinned
host's dark HUD rather than Raycast's dynamically adaptive `Color.PrimaryText`.
Light-theme adaptation and actual installed-font fallback still need GUI review.
The SVG has no external URLs, font resources or scripts. No new host image/font
resource API is required. Owned TTF/CFF OTF/TTC/WOFF/WOFF2 fixtures are generated
from new geometric outlines, parsed natively, and used in an initially empty
Rust font database: three actual V1/Rust specimen pairs render pixel-identically.
That proves bounded artifact semantics with owned fonts, not OS GUI acceptance.

## Host prerequisite — separate and unapplied

[host-prerequisites/input-ownership.patch](host-prerequisites/input-ownership.patch)
is a **generic, unapplied** patch against host revision
`ea100cee3f69711de12485ba061950c5fc65258f`. No app working file was read or changed.
The patch opts in through `root.props.inputDraft`: it advances complete draft
ownership synchronously before the 200 ms debounce, sends current search/filter/
immutable preview preference with the revision, rejects stale search/action/
refresh/load-more responses, remounts on session/generation changes, honors the
controlled dropdown value and custom empty state, and treats `unchanged` as inert
before displaying any fallback copy notice. Existing host dispatch already
forwards those payload fields unchanged. Search/draft tests cover A/B/A, invalid
intermediates, pending refresh/action responses and session changes.

**Integrate and review that patch before GUI acceptance.** The pinned unpatched
renderer can overwrite a newer draft and mishandle an inert action response.
The tests apply the patch only to source copies under `.qa`, exercise actual
ListRuntime/Markdown/ExtensionRuntimeView/ExtensionRuntimeSurface code with desktop
services stubbed before render, and check applicability to the pinned Git objects.
The host and SDK themselves remain untouched.

## Actions and lifetime

Only `clipboard.write` and `shell.reveal` are granted. Copy/reveal use their
original text/path, and success requires the closed host acknowledgement
`{ok:true,message?:string}`. Null, booleans, unknown fields, contradictory fields
and invalid message types are rejected. Actual pinned host routing, clipboard and
both platform reveal producer arms are extracted and tested with OS edges stubbed.
Windows' pinned reveal acknowledgement means successful process creation, not
proof that Explorer displayed a selection.

Action IDs are session-owned and single-use. The runtime consumes them **outside
SDK staged state before awaiting** the host. A cancellation or unknown outcome
cannot roll that consumption back. Unknown results expose an explicit frozen
retry with a possible-duplicate warning, or an effect-free dismissal. The retry
keeps the original bytes/path after search/navigation changes. An acknowledged
copy gets a fresh normal Copy action for intentional repetition. Queued, stale
and cross-session IDs are inert. This is not exactly-once or crash-durable delivery;
a process crash cannot determine whether an external action finished.

No product task, timer, helper process or background thread is created by the port.
The SDK owns its ordinary two-worker runtime and stdin pump. Cancellation guards
remove unfinished opens; cancelled scopes are pruned without a polling task.
140 opens are cancelled after entering the fixture discovery provider, without
sending dispose; all 128 session slots remain available afterward.

## Explicit bounds

* 65,536 visited entries; 4,096 directories; 8,192 candidates/fonts; 4,096 UTF-8
  bytes/path; 1,024 bytes/name. Exceeding any enumeration bound fails the catalog,
  with no silently partial discovery. Non-UTF-8 filenames/paths are explicit errors.
* Catalog cache: 12 MiB; pin/filter store: 256 KiB. Malformed data is rejected.
  Product discovery never reads individual font file contents.
* Preview and search text: 4,096 UTF-8 bytes each; SVG fixed at 600×300; no embedded
  font files. Views must serialize below 12 MiB, leaving envelope headroom under
  the SDK's 16 MiB frame cap. Accepted exact-limit and rejected oversize frames are
  exercised through the actual SDK reader.
* 128 sessions. Views page by 64 to at most 256 rows. At that bound a visible
  message states the total matching count and asks for a narrower search; **the
  complete catalog remains searchable**, including fonts beyond the visible page.
  Action dictionaries are bounded by those rows plus navigation/recovery actions.
* No port-maintained preview cache or per-font resource leases. Unknown results
  retain at most one frozen external action per session.

## Reproduce isolated verification

Use existing Rust stable and 1.85.0 toolchains, an existing Windows GNU std target,
Node/npm and Python 3.9+. No toolchain/system dependency/font installation is run.
From the clone root:

```sh
v2/scripts/qa-run.sh python3 v2/scripts/verify.py
v2/scripts/qa-run.sh python3 v2/scripts/finalize.py
```

The wrapper confines mutable HOME/TMP/XDG/Cargo/npm/pip state, disposable source
copies, generated fonts, stores and extracted packages to **this `v2/.qa`**.
Preinstalled Rust toolchains are read-only. `target/`, `.qa/`, `dist/` and Python
bytecode are ignored. Network is used only for pinned source/icon/grant retrieval
and locked dependency downloads, never a network scan or a live product API.
Npm lifecycle scripts are disabled. The V1 lock remains byte-identical in its
copy. QA dependencies are pinned in `qa/package-lock.json` and
`qa/requirements.lock` (authentic PyPI artifact hashes); their installed distributions retain their original notices.

The production binary has no fixture provider, test endpoint or environment
provider override. `font-search-qa` is a separate feature-gated binary and is never
packaged. All discovery tests use owned roots. The extracted production executable
is smoke-tested against its **normal persisted catalog**, seeded with owned fixture
records; production Reload/native OS enumeration is deliberately never invoked.

[evidence/verification.json](evidence/verification.json) records the gates;
other evidence files record source/fixture/icon hashes, complete-source oracle,
renderer checks, real SDK pipes, native preview pixels, full schema validation,
licenses, fresh build and the development ZIP member map.
`dist/font-search-aarch64-apple-darwin-dev.zip` is deterministic for identical input
bytes (fixed member order/time/mode), is closed-inventoried, and contains only the
production executable, original icon and necessary legal notices. It has no
acquisition/release URL. A fresh empty Cargo home and target build fetches the SDK
from the pinned HTTPS revision under Rust 1.85; it does not reuse sibling sources.

Native installed-font enumeration, Finder/Explorer/clipboard UI and font fallback
on real macOS/Windows hosts are **not run**. Windows GNU check/clippy passes; no
MinGW C compiler/dlltool or MSVC target/link environment is installed here, so no
Windows linking/MSVC binary claim is made. Target-inapplicable WASI dependencies
in Cargo.lock may require Rust newer than 1.85; the macOS build and QA graph is verified on 1.85. Windows GNU
check/clippy also runs on stable and 1.85.0; MSVC acceptance remains unrun.

[licenses/dependencies.json](licenses/dependencies.json) records authentic locked
Cargo grants, including the actual grant inside `r-efi`'s `AUTHORS`. Nothing is
substituted because a crate uses an unusual notice filename. The V1 root license,
lock and assets remain untouched. The icon is verified byte-for-byte against
Raycast/extensions `6734d85992290066fd31a7f5bee3cca3d3545a1a`:
`729724bc2c33449f14680faf1a38268eea1b5053d335186a9c94366bfc8ac263`.

`finalize.py` inventories every Git-visible `v2/` file and the root README, excluding
only its self-referential inventory file. It checks the unchanged V1 bytes, branch,
source SHA, ignored outputs and empty index. The parent can run
`finalize.py --check-staged` **after their own staging** to rehash the exact staged
blobs; this task never stages, commits, pushes or deletes the clone.

XERJ initially indexed every V1 source file under canonical prefix
`ax-9b415502fa8a`. Final reindex failed on frozen dataset/schema evolution when
new Rust/TOML files appeared. No alternate prefix, schema edit or server restart
was attempted; exhaustive `rg`, full file reads and pinned Git objects supplied
the final checks. See `evidence/xerj.json`.
