import { cleanName, coreName } from "./names.js";
import { transcribe } from "./transcribe.js";

/** Similarity averages (0-100) and the 0-1 scores behind them, by feature name. */
export interface SimilarityScores {
  look_alike: number;
  sound_alike: number;
  look_alike_scores: Record<string, number>;
  sound_alike_scores: Record<string, number>;
  /** Set when the typed name's pronunciation had to be estimated in the browser. */
  sound_alike_approximate?: boolean;
}

/** A candidate's score, with `index` giving its position in the full drug list. */
export interface ShardMatch {
  name: string;
  nativized: string;
  score: number;
  index: number;
  similarity: SimilarityScores | null;
}

export type WorkerReply =
  | { id: number; matches: ShardMatch[] }
  | { id: number; error: string };

interface AlineWasm {
  memory: WebAssembly.Memory;
  alloc(length: number): number;
  dealloc(pointer: number, length: number): void;
  inventory_ptr(): number;
  inventory_len(): number;
  kondrak_inventory_ptr(): number;
  kondrak_inventory_len(): number;
  score_batch(
    queryPointer: number,
    queryLength: number,
    candidatesPointer: number,
    candidatesLength: number,
    scoresPointer: number,
  ): number;
  similarities(inputPointer: number, inputLength: number): number;
  similarities_ptr(): number;
}

/** A name's spellings and Filipino IPA, as the similarity algorithms read them. */
interface ScoredName {
  clean: string;
  core: string;
  filIpa: string;
  coreIpa: string;
}

// Written by the Python backend: TagaBaybay spellings and Filipino IPA for every drug.
const DRUG_CSV = new URL("../py/data/classifier_cache.csv", import.meta.url);
const ALINE_WASM = new URL("../wasm/aline.wasm", import.meta.url);

// ALINE is too slow on one thread, so each worker scores every Nth drug.
const workerParams = new URL(import.meta.url).searchParams;
const SHARD = Number(workerParams.get("shard"));
const SHARD_COUNT = Number(workerParams.get("of"));

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function normalizeName(name: string): string {
  return name.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

function storeBytes(wasm: AlineWasm, bytes: Uint8Array): number {
  const pointer = wasm.alloc(bytes.length);
  new Uint8Array(wasm.memory.buffer).set(bytes, pointer);
  return pointer;
}

/** Read the symbols ALINE accepts. Call the pointer first: building them can grow memory. */
function readSymbols(wasm: AlineWasm, pointer: number, length: number): Set<string> {
  return new Set(decoder.decode(new Uint8Array(wasm.memory.buffer, pointer, length)));
}

function average(scores: Record<string, number>): number {
  const values = Object.values(scores);
  return (values.reduce((sum, value) => sum + value, 0) / values.length) * 100;
}

function parseSimilarities(text: string): SimilarityScores {
  const look: Record<string, number> = {};
  const sound: Record<string, number> = {};
  for (const line of text.trimEnd().split("\n")) {
    const [group, feature = "", score = "0"] = line.split("\t");
    (group === "look" ? look : sound)[feature] = Number(score);
  }
  return {
    look_alike: average(look),
    sound_alike: average(sound),
    look_alike_scores: look,
    sound_alike_scores: sound,
  };
}

function scoreSimilarities(
  wasm: AlineWasm,
  query: ScoredName,
  drug: ScoredName,
): SimilarityScores | null {
  const input = encoder.encode(
    [
      query.clean,
      drug.clean,
      query.core,
      drug.core,
      query.filIpa,
      drug.filIpa,
      query.coreIpa,
      drug.coreIpa,
    ].join("\n"),
  );
  const inputPointer = storeBytes(wasm, input);
  const length = wasm.similarities(inputPointer, input.length);
  wasm.dealloc(inputPointer, input.length);
  if (length < 0) {
    return null;
  }

  const pointer = wasm.similarities_ptr();
  return parseSimilarities(decoder.decode(new Uint8Array(wasm.memory.buffer, pointer, length)));
}

async function fetchOk(url: URL): Promise<Response> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load ${url.pathname}: ${response.status}`);
  }
  return response;
}

async function createSearch(): Promise<(query: string, limit: number) => ShardMatch[]> {
  const [wasmBytes, csvText] = await Promise.all([
    fetchOk(ALINE_WASM).then((response) => response.arrayBuffer()),
    fetchOk(DRUG_CSV).then((response) => response.text()),
  ]);

  const { instance } = await WebAssembly.instantiate(wasmBytes);
  const wasm = instance.exports as unknown as AlineWasm;
  const allowedSymbols = readSymbols(wasm, wasm.inventory_ptr(), wasm.inventory_len());
  const kondrakSymbols = readSymbols(
    wasm,
    wasm.kondrak_inventory_ptr(),
    wasm.kondrak_inventory_len(),
  );

  const drugs = csvText
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name = "", clean = "", core = "", nativized = "", filIpa = "", coreIpa = ""] =
        line.split(",");
      return { name, clean, core, nativized, filIpa, coreIpa };
    })
    .map((drug) => ({ ...drug, ipa: transcribe(drug.name, allowedSymbols).ipa }))
    .filter((drug) => drug.ipa)
    .map((drug, index) => ({ ...drug, index }));
  if (!drugs.length) {
    throw new Error("The drug list has no usable names.");
  }

  const exactMatches = new Map<string, (typeof drugs)[number]>();
  for (const drug of drugs) {
    const normalized = normalizeName(drug.name);
    if (!exactMatches.has(normalized)) {
      exactMatches.set(normalized, drug);
    }
  }

  const shard = drugs.filter((drug) => drug.index % SHARD_COUNT === SHARD);
  const candidates = encoder.encode(shard.map((drug) => drug.ipa).join("\n"));
  const candidatesPointer = storeBytes(wasm, candidates);
  const scoresPointer = wasm.alloc(shard.length * Float32Array.BYTES_PER_ELEMENT);

  const estimateName = (query: string): ScoredName => {
    const clean = cleanName(query);
    const core = coreName(clean);
    return {
      clean,
      core,
      filIpa: transcribe(clean, kondrakSymbols).ipa,
      coreIpa: transcribe(core, kondrakSymbols).ipa,
    };
  };

  return (query, limit) => {
    const exact = exactMatches.get(normalizeName(query));
    const ipa = exact?.ipa ?? transcribe(query, allowedSymbols).ipa;
    if (!ipa) {
      throw new Error("Query must contain at least one letter.");
    }

    const queryBytes = encoder.encode(ipa);
    const queryPointer = storeBytes(wasm, queryBytes);
    const written = wasm.score_batch(
      queryPointer,
      queryBytes.length,
      candidatesPointer,
      candidates.length,
      scoresPointer,
    );
    wasm.dealloc(queryPointer, queryBytes.length);
    if (written !== shard.length) {
      throw new Error("ALINE could not score this query.");
    }

    const scores = new Float32Array(wasm.memory.buffer, scoresPointer, shard.length);
    const top = shard
      .map((drug, position) => ({ drug, score: scores[position] ?? 0 }))
      .sort((first, second) => second.score - first.score)
      .slice(0, limit);

    const target = exact ?? estimateName(query);
    return top.map(({ drug, score }) => {
      const similarity = scoreSimilarities(wasm, target, drug);
      return {
        name: drug.name,
        nativized: drug.nativized,
        score,
        index: drug.index,
        similarity:
          similarity && !exact ? { ...similarity, sound_alike_approximate: true } : similarity,
      };
    });
  };
}

const search = createSearch();

self.addEventListener(
  "message",
  async (event: MessageEvent<{ id: number; query: string; limit: number }>) => {
    const { id, query, limit } = event.data;
    let reply: WorkerReply;
    try {
      reply = { id, matches: (await search)(query, limit) };
    } catch (error) {
      reply = { id, error: error instanceof Error ? error.message : "Search failed." };
    }
    self.postMessage(reply);
  },
);
