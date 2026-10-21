interface SearchResult {
  name: string;
  type: string;
  source: string;
  score: number;
}

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
const rows = getElement<HTMLTableSectionElement>("#rows");
const empty = getElement<HTMLDivElement>("#empty");

async function search(): Promise<void> {
        const query = input.value.trim();

        if(!query) {
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

            const results: SearchResult[] = await response.json();
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
        }
}

button.addEventListener("click", search);
input.addEventListener("keydown", (event: KeyboardEvent) => {
  if (event.key === "Enter") {
    void search();
  }
});