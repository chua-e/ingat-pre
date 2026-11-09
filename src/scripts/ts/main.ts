import type { ShardMatch, WorkerReply } from "./worker.js";

interface SearchResult {
  name: string;
  score: number;
  source: string;
}

const SOURCE = "ph_GenBrn";
const RESULT_LIMIT = 20;
const MAX_WORKERS = 8;

const STEMS=["-pril","-sartan","-statin","-mab","-nib","-azole","-prazole","-olol","-pine","-cillin","-azepam","-oxetine"];

function getElement<T extends HTMLElement>(selector: string): T {
    const element = document.querySelector<T>(selector);
    if (!element) {
        throw new Error(`Required page element not found: ${selector}`);
    }
    return element;
}

const input = getElement<HTMLInputElement>("#q");
const button = getElement<HTMLButtonElement>("#go");
const buttonLabel = getElement<HTMLSpanElement>("#go-label");
const spinner = getElement<HTMLSpanElement>("#loading-spinner");
const rows = getElement<HTMLTableSectionElement>("#rows");
const empty = getElement<HTMLDivElement>("#empty");

const workerCount = Math.min(navigator.hardwareConcurrency || 4, MAX_WORKERS);
const workers = Array.from(
    { length: workerCount },
    (_, shard) =>
        new Worker(new URL(`./worker.js?shard=${shard}&of=${workerCount}`, import.meta.url), {
            type: "module",
        }),
);
let nextSearchId = 0;

function askWorker(worker: Worker, id: number, query: string): Promise<ShardMatch[]> {
    return new Promise((resolve, reject) => {
        const onMessage = (event: MessageEvent<WorkerReply>) => {
            if (event.data.id !== id) {
                return;
            }
            worker.removeEventListener("message", onMessage);
            if ("error" in event.data) {
                reject(new Error(event.data.error));
            } else {
                resolve(event.data.matches);
            }
        };
        worker.addEventListener("message", onMessage);
        worker.postMessage({ id, query, limit: RESULT_LIMIT });
    });
}

async function runSearch(query: string): Promise<SearchResult[]> {
    const id = nextSearchId++;
    const shards = await Promise.all(workers.map((worker) => askWorker(worker, id, query)));
    return shards
        .flat()
        .sort((first, second) => second.score - first.score || first.index - second.index)
        .slice(0, RESULT_LIMIT)
        .map(({ name, score }) => ({
            name,
            score: Math.round(score * 10000) / 100,
            source: SOURCE,
        }));
}

async function search(): Promise<void> {
        const query = input.value.trim();

        if(!query) {
            empty.textContent = "Enter a proposed drug name to search.";
            empty.hidden = false;
            rows.replaceChildren();
            return;
        }

        button.disabled = true;
        buttonLabel.textContent = "Searching";
        spinner.hidden = false;
        empty.textContent = "Searching for similar drug names…";
        empty.hidden = false;
        rows.replaceChildren();

        try {
            const results = await runSearch(query);
            rows.replaceChildren();

            for (const result of results) {
                const row = document.createElement("tr");

                for (const value of [
                    result.name,
                    `${result.score}%`,
                    result.source,
                ]) {
                    const cell = document.createElement("td");
                    cell.textContent = value;
                    row.append(cell);
                }

                rows.append(row);
            }

            empty.textContent = results.length ? "" : "No matching drugs found.";
            empty.hidden = results.length > 0;
                
        } catch(error) {
            empty.textContent = error instanceof Error ? error.message : "Search failed.";
            empty.hidden = false;
            rows.replaceChildren();
        } finally {
            button.disabled = false;
            buttonLabel.textContent = "Search";
            spinner.hidden = true;
        }
}

button.addEventListener("click", search);
input.addEventListener("keydown", (event: KeyboardEvent) => {
  if (event.key === "Enter") {
    void search();
  }
});