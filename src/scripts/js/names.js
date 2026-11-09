// Browser port of names.py, used for typed names that aren't in the drug list.
const CORE_NAME_STOPWORDS = new Set([
    // Salts and hydrates
    "acetate", "bromide", "carbonate", "chloride", "citrate", "dihydrate",
    "dihydrochloride", "dipropionate", "fumarate", "gluconate", "hcl",
    "hydrobromide", "hydrochloride", "hydroxide", "maleate", "monohydrate",
    "mononitrate", "phosphate", "potassium", "propionate", "sodium",
    "succinate", "sulfate", "sulphate", "trihydrate", "valerate", "besilate",
    // Dosage forms and routes
    "adsorbed", "cap", "capsule", "capsules", "cream", "drops", "er", "eye",
    "formulation", "gel", "iv", "mg", "mr", "odt", "ointment", "reformulated",
    "solution", "sr", "suspension", "syrup", "tab", "tablet", "tablets",
    "topical", "xr",
    // Product qualifiers and connecting words
    "advance", "and", "ds", "for", "forte", "kids", "od", "plus", "with",
]);
// First words that identify little alone, so the core keeps the word after them.
const CORE_LEADING_WORDS = new Set([
    // Brand-style prefixes
    "bio", "co", "dr", "fin", "go", "md", "mega", "neo", "neuro", "new", "one",
    "rapid", "st", "tri",
    // Ingredient and class words shared by many products
    "calcium", "human", "insulin", "iron", "magnesium", "multivitamins",
    "potassium", "purified", "sodium", "tetanus", "vitamin", "zinc",
]);
// Words that cannot complete a leading word: forms, routes, and qualifiers.
const CORE_LEADING_EXCLUDED = new Set([
    "adsorbed", "advance", "and", "cap", "capsule", "capsules", "cream", "drops",
    "ds", "er", "eye", "for", "formulation", "forte", "gel", "iv", "kids", "mg",
    "mr", "od", "odt", "ointment", "plus", "reformulated", "solution", "sr",
    "suspension", "syrup", "tab", "tablet", "tablets", "topical", "with", "xr",
]);
function isUsable(word, excluded) {
    return !excluded.has(word) && !/\d/.test(word) && word.length > 1;
}
/** Lowercase a name, drop accents and punctuation, and collapse whitespace. */
export function cleanName(name) {
    return name
        .toLowerCase()
        .trim()
        .normalize("NFKD")
        .replace(/\p{M}/gu, "")
        .replace(/[-/']/g, " ")
        .replace(/[^a-z0-9 ]/g, "")
        .replace(/\s+/g, " ")
        .trim();
}
/** The part of a cleaned drug name that identifies the product. */
export function coreName(name) {
    const words = name.split(" ").filter(Boolean);
    const [first = ""] = words;
    if (CORE_LEADING_WORDS.has(first)) {
        const next = words.slice(1).find((word) => isUsable(word, CORE_LEADING_EXCLUDED));
        return next ? `${first} ${next}` : first;
    }
    return words.find((word) => isUsable(word, CORE_NAME_STOPWORDS)) ?? first;
}
//# sourceMappingURL=names.js.map