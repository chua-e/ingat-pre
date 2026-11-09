// Browser port of legacy_tagabaybay.nativize, TagalogG2P and query_to_fil_ipa.

const PHONEME_RULES: ReadonlyArray<readonly [string, string]> = [
  ["ph", "f"],
  ["ps", "s"],
  ["v", "b"],
  ["j", "dy"],
  ["z", "s"],
  ["ñ", "ny"],
  ["qu", "kuw"],
];

function nativizeWord(word: string): string {
  let result = word;

  for (const [pattern, replacement] of PHONEME_RULES) {
    result = result.replaceAll(pattern, replacement);
  }

  result = result
    .replace(/^x/, "s")
    .replace(/(?<=x)y/g, "i")
    .replace(/x/g, "ks")
    .replace(/y(?=s)/g, "i")
    .replace(/y(?=l)/g, "i")
    .replace(/c([eyi])/g, "s$1")
    .replaceAll("c", "k")
    .replaceAll("kh", "k")
    .replace(/y/g, "ay")
    .replace(/(?<!a)y/g, "i")
    .replace(/g([eiy])(?![sck])/g, "dy$1")
    .replace(/ate$/, "eyt")
    .replace(/ide$/, "ayd")
    .replace(/one$/, "own")
    .replace(/e$/, "")
    .replace(/thi([ao])/g, "tay$1")
    .replaceAll("th", "t")
    .replace(/([^\d])\1/g, "$1")
    .replaceAll("ein", "in")
    .replace(/o([aeiou])(?![aeiou])/g, "oy$1")
    .replace(/i([aeiou])/g, "iy$1")
    .replace(/u([aeiou])/g, "uw$1")
    .replaceAll("eu", "u")
    .replace(/ee/g, "i")
    .replace(/oo/g, "u")
    .replace(/tion$/, "syon")
    .replace(/sion$/, "syon")
    .replace(/ture$/, "tyur")
    .replace(/ble$/, "bol");

  for (const consonant of "bdfghjklmnpqrstvwxz") {
    result = result.replaceAll(consonant.repeat(3), consonant);
  }

  return result;
}

const MULTI_LETTER_SOUNDS = new Map([
  ["ngg", "ŋg"],
  ["ngk", "ŋk"],
  ["ng", "ŋ"],
  ["ts", "ts"],
  ["dy", "dj"],
  ["ty", "tj"],
]);

const LETTER_SOUNDS = new Map([
  ...[..."ptkbfdgmnshlwaeiou"].map((letter) => [letter, letter] as const),
  ["r", "ɾ"],
  ["y", "j"],
  ["-", "."],
]);

function spellingToIpa(spelling: string): string {
  const word = spelling
    .replace(/[áà]/g, "a")
    .replace(/[éè]/g, "e")
    .replace(/[íì]/g, "i")
    .replace(/[óò]/g, "o")
    .replace(/[úù]/g, "u")
    .replaceAll("ñ", "ny");

  let ipa = "";
  let index = 0;
  while (index < word.length) {
    const three = MULTI_LETTER_SOUNDS.get(word.slice(index, index + 3));
    const two = MULTI_LETTER_SOUNDS.get(word.slice(index, index + 2));
    if (three !== undefined) {
      ipa += three;
      index += 3;
    } else if (two !== undefined) {
      ipa += two;
      index += 2;
    } else {
      ipa += LETTER_SOUNDS.get(word.charAt(index)) ?? "";
      index += 1;
    }
  }
  return ipa;
}

export interface Transcription {
  nativized: string;
  /** Filipino IPA, restricted to symbols ALINE accepts. */
  ipa: string;
}

export function transcribe(name: string, allowedSymbols: ReadonlySet<string>): Transcription {
  const nativized = name.toLowerCase().split(" ").map(nativizeWord).join(" ").trim();
  const ipa = spellingToIpa(nativized);
  const withOnset = /^[aeiou]/.test(ipa) ? `ʔ${ipa}` : ipa;
  return {
    nativized,
    ipa: [...withOnset].filter((symbol) => allowedSymbols.has(symbol)).join(""),
  };
}
