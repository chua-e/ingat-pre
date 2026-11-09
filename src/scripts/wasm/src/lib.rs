//! Browser build of pho's similarity algorithms.
//!
//! The sources are compiled directly from the `vendor/pho` submodule. The full
//! pho crate pulls in dependencies that don't target WebAssembly.

#![allow(dead_code)]

#[path = "../../../../vendor/pho/src/algorithms/aline/mod.rs"]
pub mod aline;
#[path = "../../../../vendor/pho/src/algorithms/bisim/mod.rs"]
pub mod bisim;
#[path = "../../../../vendor/pho/src/algorithms/editex/mod.rs"]
pub mod editex;
#[path = "../../../../vendor/pho/src/error.rs"]
pub mod error;
#[path = "../../../../vendor/pho/src/algorithms/lcsubstring.rs"]
pub mod lcsubstring;
#[path = "../../../../vendor/pho/src/algorithms/lcsuf.rs"]
pub mod lcsuf;
#[path = "../../../../vendor/pho/src/algorithms/levenshtein/mod.rs"]
pub mod levenshtein;
#[path = "../../../../vendor/pho/src/utils/normalize.rs"]
mod normalize;
#[path = "../../../../vendor/pho/src/algorithms/prefix/mod.rs"]
pub mod prefix;
#[path = "../../../../vendor/pho/src/algorithms/traits.rs"]
mod traits;
#[path = "../../../../vendor/pho/src/utils/validate.rs"]
mod validate;
#[path = "../../../../vendor/pho/src/algorithms/visual/mod.rs"]
pub mod visual;

pub use error::{Error, Result};

// pho's code refers to these paths from its crate root.
pub mod algorithms {
    pub use crate::traits::Algorithm;
    pub use crate::{aline, bisim};
}
pub mod utils {
    pub(crate) use crate::{normalize, validate};
}

use std::alloc::Layout;
use std::fmt::Write;
use std::sync::{Mutex, OnceLock};

use algorithms::Algorithm;
use aline::config::Aline;
use bisim::config::BiSim;
use editex::config::Editex;
use lcsubstring::LCSubstring;
use lcsuf::LCSuf;
use levenshtein::config::Levenshtein;
use prefix::config::Prefix;
use serde::de::DeserializeOwned;
use visual::config::VisualWeighted;

const CONFIG: &str = include_str!("../../py/phoc_configs/aline_cangu.toml");
const KONDRAK_CONFIG: &str = include_str!("../../py/classifier_configs/aline_kondrak.toml");
const KONDRAK_FEATURE: &str = "aline_var:kondrak_g2p:fil_na";

fn config() -> &'static Aline {
    static PARSED: OnceLock<Aline> = OnceLock::new();
    PARSED.get_or_init(|| toml::from_str(CONFIG).expect("aline_cangu.toml must be valid"))
}

fn kondrak() -> &'static Aline {
    static PARSED: OnceLock<Aline> = OnceLock::new();
    PARSED.get_or_init(|| toml::from_str(KONDRAK_CONFIG).expect("aline_kondrak.toml must be valid"))
}

fn symbols_of(config: &Aline) -> String {
    let mut symbols: String = config.sounds.keys().map(String::as_str).collect();
    symbols.push_str("ː .");
    symbols
}

fn inventory() -> &'static str {
    static SYMBOLS: OnceLock<String> = OnceLock::new();
    SYMBOLS.get_or_init(|| symbols_of(config()))
}

fn kondrak_inventory() -> &'static str {
    static SYMBOLS: OnceLock<String> = OnceLock::new();
    SYMBOLS.get_or_init(|| symbols_of(kondrak()))
}

/// Every character the main ALINE config accepts, as UTF-8.
#[unsafe(no_mangle)]
pub extern "C" fn inventory_ptr() -> *const u8 {
    inventory().as_ptr()
}

#[unsafe(no_mangle)]
pub extern "C" fn inventory_len() -> usize {
    inventory().len()
}

/// Every character the Kondrak ALINE config accepts, as UTF-8.
#[unsafe(no_mangle)]
pub extern "C" fn kondrak_inventory_ptr() -> *const u8 {
    kondrak_inventory().as_ptr()
}

#[unsafe(no_mangle)]
pub extern "C" fn kondrak_inventory_len() -> usize {
    kondrak_inventory().len()
}

// 4-byte alignment lets the same buffers back a Float32Array.
fn layout(len: usize) -> Layout {
    Layout::from_size_align(len.max(1), 4).expect("buffer size must be valid")
}

#[unsafe(no_mangle)]
pub extern "C" fn alloc(len: usize) -> *mut u8 {
    unsafe { std::alloc::alloc(layout(len)) }
}

/// # Safety
/// `pointer` and `len` must come from a matching call to [`alloc`].
#[unsafe(no_mangle)]
pub unsafe extern "C" fn dealloc(pointer: *mut u8, len: usize) {
    unsafe { std::alloc::dealloc(pointer, layout(len)) };
}

/// # Safety
/// The range must be valid UTF-8 that outlives the returned string.
unsafe fn text<'a>(pointer: *const u8, len: usize) -> &'a str {
    unsafe { std::str::from_utf8_unchecked(std::slice::from_raw_parts(pointer, len)) }
}

/// Scores `query` against newline-separated `candidates`, writing one `f32`
/// per candidate to `out`. Returns the number written, or -1 on an unknown symbol.
///
/// # Safety
/// The string ranges must be valid UTF-8 and `out` must have room for one
/// aligned `f32` per candidate.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn score_batch(
    query_ptr: *const u8,
    query_len: usize,
    candidates_ptr: *const u8,
    candidates_len: usize,
    out: *mut f32,
) -> i32 {
    let (query, candidates) =
        unsafe { (text(query_ptr, query_len), text(candidates_ptr, candidates_len)) };

    let aline = config();
    let mut written = 0;
    for candidate in candidates.split('\n') {
        let Ok(score) = aline.similarity(query, candidate) else {
            return -1;
        };
        unsafe { out.add(written).write(score) };
        written += 1;
    }
    written as i32
}

/// One spelling-based algorithm, from the classifier's phoc configs.
struct Scorer {
    feature: &'static str,
    group: &'static str,
    on_full_name: bool,
    algorithm: Box<dyn Algorithm>,
}

fn scorer<T: Algorithm + DeserializeOwned + 'static>(
    feature: &'static str,
    group: &'static str,
    on_full_name: bool,
    config: &str,
) -> Scorer {
    let algorithm = Box::new(toml::from_str::<T>(config).expect("classifier config must be valid"));
    Scorer { feature, group, on_full_name, algorithm }
}

fn scorers() -> &'static [Scorer] {
    macro_rules! config {
        ($stem:literal) => {
            include_str!(concat!("../../py/classifier_configs/", $stem, ".toml"))
        };
    }
    static SCORERS: OnceLock<Vec<Scorer>> = OnceLock::new();
    SCORERS.get_or_init(|| {
        vec![
            scorer::<LCSubstring>("lcsubstring", "look", true, config!("lcsubstring")),
            scorer::<LCSuf>("lcsuf", "look", true, config!("lcsuf")),
            // The classifier only uses unseparated Levenshtein on core words.
            scorer::<Levenshtein>("levenshtein", "look", false, config!("levenshtein")),
            scorer::<Levenshtein>(
                "levenshtein_consonant",
                "look",
                true,
                config!("levenshtein_consonant"),
            ),
            scorer::<Prefix>("prefix", "look", true, config!("prefix")),
            scorer::<VisualWeighted>("visual_weighted", "look", true, config!("visual_weighted")),
            scorer::<BiSim>("bisim", "sound", true, config!("bisim")),
            scorer::<Editex>("editex", "sound", true, config!("editex")),
        ]
    })
}

/// Tab-separated "group, feature, score" lines for one pair. `input` holds eight
/// lines: both full names, both core words, both IPAs, both core-word IPAs.
fn describe(input: &str) -> Option<String> {
    let fields: Vec<&str> = input.split('\n').collect();
    let [name_a, name_b, core_a, core_b, ipa_a, ipa_b, core_ipa_a, core_ipa_b] = fields[..] else {
        return None;
    };

    let mut lines = Vec::new();
    for scorer in scorers().iter().filter(|scorer| scorer.on_full_name) {
        let score = scorer.algorithm.similarity(name_a, name_b).ok()?;
        lines.push((scorer.group, scorer.feature.to_string(), score));
    }
    for scorer in scorers() {
        let score = scorer.algorithm.similarity(core_a, core_b).ok()?;
        lines.push((scorer.group, format!("core_{}", scorer.feature), score));
    }
    let aline = kondrak();
    lines.push(("sound", KONDRAK_FEATURE.to_string(), aline.similarity(ipa_a, ipa_b).ok()?));
    lines.push((
        "sound",
        format!("core_{KONDRAK_FEATURE}"),
        aline.similarity(core_ipa_a, core_ipa_b).ok()?,
    ));

    let mut description = String::new();
    for (group, feature, score) in lines {
        writeln!(description, "{group}\t{feature}\t{score}").ok()?;
    }
    Some(description)
}

static SIMILARITIES: Mutex<String> = Mutex::new(String::new());

/// Prepares every similarity score for one pair and returns the text's length
/// in bytes, or -1 if a score can't be produced. Read it with [`similarities_ptr`].
///
/// # Safety
/// The range must be valid UTF-8.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn similarities(input_ptr: *const u8, input_len: usize) -> i32 {
    let Some(description) = describe(unsafe { text(input_ptr, input_len) }) else {
        return -1;
    };
    let length = description.len() as i32;
    *SIMILARITIES.lock().expect("wasm is single-threaded") = description;
    length
}

#[unsafe(no_mangle)]
pub extern "C" fn similarities_ptr() -> *const u8 {
    SIMILARITIES.lock().expect("wasm is single-threaded").as_ptr()
}
