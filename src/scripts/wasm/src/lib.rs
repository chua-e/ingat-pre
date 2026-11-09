//! Browser build of pho's ALINE with the weights in `aline_cangu.toml`.
//!
//! The ALINE sources are compiled directly from the `vendor/pho` submodule. The
//! full pho crate pulls in dependencies that don't target WebAssembly.

#![allow(dead_code)]

#[path = "../../../../vendor/pho/src/algorithms/aline/mod.rs"]
pub mod aline;
#[path = "../../../../vendor/pho/src/error.rs"]
pub mod error;
#[path = "../../../../vendor/pho/src/algorithms/traits.rs"]
mod traits;
#[path = "../../../../vendor/pho/src/utils/validate.rs"]
mod validate;

pub use error::{Error, Result};

// pho's ALINE code refers to these paths from its crate root.
pub mod algorithms {
    pub use crate::aline;
    pub use crate::traits::Algorithm;
}
pub mod utils {
    pub(crate) use crate::validate;
}

use std::alloc::Layout;
use std::sync::OnceLock;

use aline::config::Aline;
use algorithms::Algorithm;

const CONFIG: &str = include_str!("../../py/phoc_configs/aline_cangu.toml");

fn config() -> &'static Aline {
    static PARSED: OnceLock<Aline> = OnceLock::new();
    PARSED.get_or_init(|| toml::from_str(CONFIG).expect("aline_cangu.toml must be valid"))
}

fn inventory() -> &'static str {
    static SYMBOLS: OnceLock<String> = OnceLock::new();
    SYMBOLS.get_or_init(|| {
        let mut symbols: String = config().sounds.keys().map(String::as_str).collect();
        symbols.push_str("ː .");
        symbols
    })
}

/// Every character ALINE accepts, as UTF-8.
#[unsafe(no_mangle)]
pub extern "C" fn inventory_ptr() -> *const u8 {
    inventory().as_ptr()
}

#[unsafe(no_mangle)]
pub extern "C" fn inventory_len() -> usize {
    inventory().len()
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
    let (query, candidates) = unsafe {
        (
            std::str::from_utf8_unchecked(std::slice::from_raw_parts(query_ptr, query_len)),
            std::str::from_utf8_unchecked(std::slice::from_raw_parts(
                candidates_ptr,
                candidates_len,
            )),
        )
    };

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
