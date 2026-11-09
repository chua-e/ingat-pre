const SOURCE = "ph_GenBrn";
const RESULT_LIMIT = 20;
const MAX_WORKERS = 8;
// CatBoost's default decision boundary.
const LIKELY_LASA_PERCENT = 50;
function getElement(selector) {
    const element = document.querySelector(selector);
    if (!element) {
        throw new Error(`Required page element not found: ${selector}`);
    }
    return element;
}
const input = getElement("#q");
const button = getElement("#go");
const buttonLabel = getElement("#go-label");
const spinner = getElement("#loading-spinner");
const rows = getElement("#rows");
const empty = getElement("#empty");
const nativizedHead = getElement("#nativized-head");
const scoreHead = getElement("#score-head");
const arrangeOptions = getElement("#arrange");
const showNativized = getElement("#show-nativized");
const showBreakdown = getElement("#show-breakdown");
let workers = [];
let nextSearchId = 0;
let currentResults = [];
let usingClassifier = false;
function startWorkers() {
    const workerCount = Math.min(navigator.hardwareConcurrency || 4, MAX_WORKERS);
    workers = Array.from({ length: workerCount }, (_, shard) => new Worker(new URL(`./worker.js?shard=${shard}&of=${workerCount}`, import.meta.url), {
        type: "module",
    }));
}
// The classifier needs the Python backend. A static host has no such route, so
// the page falls back to scoring with ALINE in the browser.
const classifierAvailable = fetch("api/health").then((response) => response.ok, () => false);
void classifierAvailable.then((available) => {
    if (available) {
        usingClassifier = true;
        scoreHead.textContent = "LASA probability";
        arrangeOptions.hidden = false;
    }
    else {
        startWorkers();
    }
});
function askWorker(worker, id, query) {
    return new Promise((resolve, reject) => {
        const onMessage = (event) => {
            if (event.data.id !== id) {
                return;
            }
            worker.removeEventListener("message", onMessage);
            if ("error" in event.data) {
                reject(new Error(event.data.error));
            }
            else {
                resolve(event.data.matches);
            }
        };
        worker.addEventListener("message", onMessage);
        worker.postMessage({ id, query, limit: RESULT_LIMIT });
    });
}
async function runClassifierSearch(query) {
    const response = await fetch("api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
    });
    if (!response.ok) {
        const body = (await response.json().catch(() => null));
        throw new Error(typeof body?.detail === "string" ? body.detail : "Search failed.");
    }
    const results = (await response.json());
    return results.map(({ name, nativized, score, source, ...similarity }) => ({
        name,
        nativized,
        score,
        source,
        similarity,
    }));
}
async function runBrowserSearch(query) {
    const id = nextSearchId++;
    const shards = await Promise.all(workers.map((worker) => askWorker(worker, id, query)));
    return shards
        .flat()
        .sort((first, second) => second.score - first.score || first.index - second.index)
        .slice(0, RESULT_LIMIT)
        .map(({ name, nativized, score, similarity }) => ({
        name,
        nativized,
        score: Math.round(score * 10000) / 100,
        source: SOURCE,
        similarity,
    }));
}
function inputLabel(feature) {
    const name = feature
        .replace(/^core_/, "")
        .replace(/^aline_var:.*$/, "aline (Filipino)")
        .replaceAll("_", " ");
    return feature.startsWith("core_") ? `${name}, core word` : name;
}
function inputGroup(title, scores) {
    const heading = document.createElement("h3");
    heading.textContent = title;
    const list = document.createElement("dl");
    list.className = "inputs";
    for (const [feature, value] of Object.entries(scores)) {
        const item = document.createElement("div");
        const name = document.createElement("dt");
        name.textContent = inputLabel(feature);
        const score = document.createElement("dd");
        score.textContent = Number.isInteger(value) ? String(value) : value.toFixed(3);
        item.append(name, score);
        list.append(item);
    }
    const group = document.createDocumentFragment();
    group.append(heading, list);
    return group;
}
function breakdownElement(result) {
    const container = document.createElement("div");
    container.className = "breakdown";
    if (result.similarity) {
        container.append(inputGroup("Look-alike", result.similarity.look_alike_scores), inputGroup("Sound-alike", result.similarity.sound_alike_scores));
    }
    else {
        const message = document.createElement("p");
        message.textContent = "No breakdown is available for this drug.";
        container.append(message);
    }
    return container;
}
function soundAlikeContent(similarity) {
    const value = `${similarity.sound_alike.toFixed(1)}%`;
    if (!similarity.sound_alike_approximate) {
        return value;
    }
    const approximate = document.createElement("span");
    approximate.title = "Approximate: this name isn't in the drug list, so its pronunciation is estimated.";
    approximate.textContent = `≈${value}`;
    return approximate;
}
function scoreContent(result) {
    const score = `${result.score}%`;
    if (!usingClassifier || result.score < LIKELY_LASA_PERCENT) {
        return score;
    }
    const warning = document.createElement("span");
    warning.className = "warning";
    warning.title = `The classifier's probability is ${LIKELY_LASA_PERCENT}% or higher`;
    warning.textContent = "⚠ Likely LASA";
    const content = document.createDocumentFragment();
    content.append(score, warning);
    return content;
}
function arrangedResults() {
    const arrangement = arrangeOptions.querySelector(":checked")?.value;
    const measure = (result) => {
        if (arrangement === "look" && result.similarity) {
            return result.similarity.look_alike;
        }
        if (arrangement === "sound" && result.similarity) {
            return result.similarity.sound_alike;
        }
        return result.score;
    };
    return [...currentResults]
        .sort((first, second) => measure(second) - measure(first))
        .slice(0, RESULT_LIMIT);
}
function renderResults() {
    const includeNativized = showNativized.checked;
    nativizedHead.hidden = !includeNativized;
    rows.replaceChildren(...arrangedResults().flatMap((result, position) => {
        const row = document.createElement("tr");
        const values = [
            result.name,
            ...(includeNativized ? [result.nativized] : []),
            ...(result.similarity
                ? [
                    `${result.similarity.look_alike.toFixed(1)}%`,
                    soundAlikeContent(result.similarity),
                ]
                : ["–", "–"]),
            scoreContent(result),
            result.source,
        ];
        for (const value of values) {
            const cell = document.createElement("td");
            cell.append(value);
            row.append(cell);
        }
        const rendered = [row];
        if (showBreakdown.checked) {
            const detail = document.createElement("tr");
            detail.className = "detail";
            const cell = document.createElement("td");
            cell.colSpan = values.length;
            cell.append(breakdownElement(result));
            detail.append(cell);
            rendered.push(detail);
        }
        if (position % 2 === 1) {
            rendered.forEach((element) => element.classList.add("alt"));
        }
        return rendered;
    }));
}
function showResults(results) {
    currentResults = results;
    renderResults();
}
async function search() {
    const query = input.value.trim();
    if (!query) {
        empty.textContent = "Enter a proposed drug name to search.";
        empty.hidden = false;
        showResults([]);
        return;
    }
    button.disabled = true;
    buttonLabel.textContent = "Searching";
    spinner.hidden = false;
    empty.textContent = "Searching for similar drug names…";
    empty.hidden = false;
    showResults([]);
    try {
        const results = await ((await classifierAvailable)
            ? runClassifierSearch(query)
            : runBrowserSearch(query));
        showResults(results);
        empty.textContent = results.length ? "" : "No matching drugs found.";
        empty.hidden = results.length > 0;
    }
    catch (error) {
        empty.textContent = error instanceof Error ? error.message : "Search failed.";
        empty.hidden = false;
        showResults([]);
    }
    finally {
        button.disabled = false;
        buttonLabel.textContent = "Search";
        spinner.hidden = true;
    }
}
arrangeOptions.addEventListener("change", renderResults);
showNativized.addEventListener("change", renderResults);
showBreakdown.addEventListener("change", renderResults);
button.addEventListener("click", search);
input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        void search();
    }
});
export {};
//# sourceMappingURL=main.js.map