const STEMS = ["-pril", "-sartan", "-statin", "-mab", "-nib", "-azole", "-prazole", "-olol", "-pine", "-cillin", "-azepam", "-oxetine"];
function getElement(selector) {
    const element = document.querySelector(selector);
    if (!element) {
        throw new Error(`Required page element not found: ${selector}`);
    }
    return element;
}
const input = getElement("#q");
const button = getElement("#go");
const rows = getElement("#rows");
const empty = getElement("#empty");
async function search() {
    const query = input.value.trim();
    if (!query) {
        empty.textContent = "Enter a proposed drug name to search.";
        empty.hidden = false;
        rows.replaceChildren();
        return;
    }
    button.disabled = true;
    try {
        const response = await fetch("http://127.0.0.1:8000/api/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query }),
        });
        if (!response.ok) {
            throw new Error(`Search failed: ${response.status}`);
        }
        const results = await response.json();
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
    }
    catch (error) {
        empty.textContent = error instanceof Error ? error.message : "Search failed.";
        empty.hidden = false;
        rows.replaceChildren();
    }
    finally {
        button.disabled = false;
    }
}
button.addEventListener("click", search);
input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        void search();
    }
});
export {};
//# sourceMappingURL=main.js.map