import { toFilipinoIpa } from "./transcribe.js";

/** A candidate's score, with `index` giving its position in the full drug list. */
export interface ShardMatch {
  name: string;
  score: number;
  index: number;
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
  score_batch(
    queryPointer: number,
    queryLength: number,
    candidatesPointer: number,
    candidatesLength: number,
    scoresPointer: number,
  ): number;
}

const DRUG_CSV = new URL("../py/data/ph_GenBrn.csv", import.meta.url);
const ALINE_WASM = new URL("../wasm/aline.wasm", import.meta.url);

// ALINE is too slow on one thread, so each worker scores every Nth drug.
const workerParams = new URL(import.meta.url).searchParams;
const SHARD = Number(workerParams.get("shard"));
const SHARD_COUNT = Number(workerParams.get("of"));

const encoder = new TextEncoder();

function normalizeName(name: string): string {
  return name.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

function storeBytes(wasm: AlineWasm, bytes: Uint8Array): number {
  const pointer = wasm.alloc(bytes.length);
  new Uint8Array(wasm.memory.buffer).set(bytes, pointer);
  return pointer;
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
  // Call these before reading memory.buffer: building the inventory can grow it.
  const inventoryPointer = wasm.inventory_ptr();
  const inventoryLength = wasm.inventory_len();
  const allowedSymbols = new Set(
    new TextDecoder().decode(new Uint8Array(wasm.memory.buffer, inventoryPointer, inventoryLength)),
  );

  const drugs = csvText
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((name) => ({ name, ipa: toFilipinoIpa(name, allowedSymbols) }))
    .filter((drug) => drug.ipa)
    .map((drug, index) => ({ ...drug, index }));
  if (!drugs.length) {
    throw new Error("The drug list has no usable names.");
  }

  const exactMatches = new Map<string, string>();
  for (const drug of drugs) {
    const normalized = normalizeName(drug.name);
    if (!exactMatches.has(normalized)) {
      exactMatches.set(normalized, drug.ipa);
    }
  }

  const shard = drugs.filter((drug) => drug.index % SHARD_COUNT === SHARD);
  const candidates = encoder.encode(shard.map((drug) => drug.ipa).join("\n"));
  const candidatesPointer = storeBytes(wasm, candidates);
  const scoresPointer = wasm.alloc(shard.length * Float32Array.BYTES_PER_ELEMENT);

  return (query, limit) => {
    const ipa = exactMatches.get(normalizeName(query)) ?? toFilipinoIpa(query, allowedSymbols);
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
    return shard
      .map((drug, position) => ({
        name: drug.name,
        score: scores[position] ?? 0,
        index: drug.index,
      }))
      .sort((first, second) => second.score - first.score)
      .slice(0, limit);
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
