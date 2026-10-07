// Extracts declarations VERBATIM from the delivered app (cinemeter-v7_8.html)
// into cinemeter-logic.mjs so the unit tests exercise the real shipped code.
// Usage: node extract.mjs ../cinemeter-v7_8.html
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { findDecl as findIn } from "./lib-extract.mjs";

const htmlPath = process.argv[2] || "../cinemeter-v7_8.html";
const html = readFileSync(htmlPath, "utf8");
const start = html.indexOf('<script type="module">');
const end = html.lastIndexOf("</script>");
const src = html.slice(start + '<script type="module">'.length, end);
const scriptLineOffset = html.slice(0, start).split("\n").length; // line of <script> in the HTML

const NAMES = [
  // Firestore REST client (query building) — network calls (fsFetch/getDocs/getDoc) are replaced by a fake DB
  "DOC_ID", "db", "documentId", "collection", "doc", "where", "orderBy", "limit", "startAt", "startAfter", "endAt", "query",
  "OP_MAP", "toFsValue", "fromFsValue", "fromFsFields", "fieldRef", "makeSnapshot", "cursorValues", "buildStructuredQuery",
  // config / state
  "GEMINI_PRIMARY_MODEL", "GEMINI_FALLBACK_MODELS", "algoliaReady",
  "PAGE_SIZE", "POOL_SIZE", "MAX_AUTO_PAGES", "MAX_SCAN_PAGES", "EQ_WINDOW", "ALGOLIA_MAX_FILTER_PAGES", "HERO_MIN_VOTES",
  "TRENDING_YEAR_SPAN", "TRENDING_MIN_POPULARITY", "HERO_YEAR_SPAN", "HERO_SCAN", "CACHE_TTL_MS", "SD_RULES", "DISCOVERY",
  "targetCollection", "collectionResolved", "latestYear",
  "VOTE_KEYS", "POPULARITY_KEYS", "TMDBID_KEYS", "KEYWORD_KEYS", "MEDIATYPE_KEYS",
  "votesField", "mediaField", "mediaServerFilter", "votesNumeric", "hasPopularityField", "?hasScoreFields",
  "loadedMovies", "lastVisibleDoc", "exhausted", "loading", "autoPagesLoaded", "requestId", "randomSeedId", "heroPool",
  "searchQuery", "activeFilters", "pageCache", "genreSDCache", "FILTER_LABELS", "VALUE_LABELS",
  "GENRE_VARIANTS", "GENRE_CANONICAL", "GENRE_DISPLAY_TH", "genresArrayReady", "THAI_CHAR", "THAI_TONE_MARKS",
  "brokenStrategies", "HERO_STORAGE_KEY", "HERO_QUEUE_KEY", "HERO_POOL_KEY", "lastHeroId", "heroQueue",
  "HOME_ROWS", "ROW_SIZE", "rowState", "lastOpenedMovie", "currentDetail", "ERA_SPAN", "ERA_HARD_LIMIT", "SIMILAR_SYSTEM",
  "geminiModel", "GENRE_MAP", "PLAN_SYSTEM", "CHAT_SYSTEM_PROMPT",
  // helpers
  "?idLooksImdb", "toNum", "toNumOrNull", "pickField", "getVotes", "getPopularity", "getTmdbId", "getMediaType", "isSeries", "getKeywords",
  "getYear", "formatVotes", "getEnglishTitle", "getThaiTitle", "docToMovie", "setStatus", "randomDocId", "yearInValues",
  "genreValues", "canonicalGenre", "legacyGenres", "movieGenres", "genreLabelTH", "genreDisplay", "genreWhere",
  "yearsFromFilter", "escapeHtml", "matchesGenre", "matchesMedia", "passesFilters", "hasClientFilters", "snapshotFilters",
  "filterKey",
  // schema detection & querying
  "detectValidCollection", "detectSchema", "detectGenresArray", "detectLatestYear", "reportIndexError", "runQuerySafe",
  // search
  "stripThaiTones", "algoliaQuery", "searchAlgolia", "normTitle", "titleMatchTier", "sortSearchHits", "loadSearch", "searchByTitle",
  // filter / ranking layer
  "serverWheres", "strategiesFor", "strategyNeedsClient", "sliceBuffer", "fetchEqWindows", "queryFiltered",
  "trustBoost", "rankOrderField", "rankSorter", "trendingYears", "isTrendingMode", "loadTrending", "loadRanked", "loadDiscovery",
  // main fetch + rendering used by it
  "fetchMovies", "renderSkeleton", "renderTop10", "updateHomeRows", "buildHomeRows", "renderGrid", "buildCard", "updateGridHeader",
  // hero
  "readStore", "writeStore", "isHeroCandidate", "buildHeroPool", "shuffled", "pickHero",
  // personalized (PERS-01, v7_9 เท่านั้น)
  "?TASTE_KEY", "?TASTE", "?readTaste", "?addGenreScore", "?recordTaste", "?toggleLike", "?topGenres", "?mixForYou", "?forYouRow", "?FOR_YOU_SEEDS", "?likedRow", "?loadMoviesByIds", "?LANG_POOL", "?getLanguage", "?forYouScore", "?loadSameLanguage", "?similarCache", "?similarToLiked",
  "rowFilters", "loadHomeRow", "?homeRowsNow", "?FAMILY_CARTOON", "?homeShown", "?homePending", "?familyCartoonOutOfPlace", "?pickRowMovies", "?shownAbove", "?loadHomeRowNow",
  "?FAMILIAR", "?getCollectionId", "?getCompanies", "?sameCollection", "?companyOverlap", "?keepFamiliar", "?sortByRelease", "?loadCollection", "?renderCollectionRow",
  // recommend side
  "getGenreSD", "decideTrustSide", "isDetailOpen",
  // similarity ("If you like…")
  "eraCloseness", "keywordOverlap", "genreOverlap", "preScore", "eraTag", "fallbackRank", "buildCandidatePool", "fetchSimilarMovies",
  // chatbot
  "parseJsonLoose", "roundOrNull", "getCurrentMovieContext", "compactMovie", "buildChatPrompt", "candidatesFromPlan",
  "extractReply", "answerWithGemini", "answerOffline",
];

const findDecl = n => { const opt = n.startsWith("?"); try { return findIn(src, n.replace("?", ""), scriptLineOffset); } catch (e) { if (opt) return null; throw e; } };
const decls = NAMES.map(findDecl).filter(Boolean).sort((a, b) => a.line - b.line);
const letNames = decls.filter(d => /^let\s/.test(d.code)).map(d => d.name);

const header = `// AUTO-GENERATED by extract.mjs from ${htmlPath.split("/").pop()} — do not edit.
// Every declaration below "verbatim app code" is copied unchanged from the app (in original order).
// Only the stubs in this header are test scaffolding: network (Firestore/Algolia/Gemini) is replaced by fakes.
// source sha256: ${createHash("sha256").update(html).digest("hex").slice(0, 16)}
/* ---------- test scaffolding (not app code) ---------- */
const firebaseConfig = { projectId: "movie-858f6" };          // real config has API keys — not copied
const ALGOLIA = { appId: "", searchKey: "", indexName: "" };   // Algolia disabled -> Firestore search path
let __getDocs = async () => { throw new Error("no fake db installed"); };
let __getDoc = async (ref) => ({ id: ref.path.split("/").pop(), exists: () => false, data: () => undefined });
let __gemini = async () => { throw new Error("gemini offline"); };
async function getDocs(q) { return __getDocs(q); }
async function getDoc(ref) { return __getDoc(ref); }
async function callGemini(opts) { return __gemini(opts); }
/* ---------- verbatim app code ---------- */
`;

const body = decls.map(d => `// ↓ ${d.name} — ${htmlPath.split("/").pop()} line ${d.line}\n${d.code}`).join("\n\n");

const footer = `
/* ---------- test hooks ---------- */
export const __hooks = {
  algolia: ALGOLIA,
  setGetDocs(fn) { __getDocs = fn; },
  setGetDoc(fn) { __getDoc = fn; },
  setGemini(fn) { __gemini = fn; },
  set(k, v) {
    switch (k) {
${letNames.map(n => `      case "${n}": ${n} = v; break;`).join("\n")}
      default: throw new Error("unknown state " + k);
    }
  },
  get(k) {
    return ({ ${letNames.join(", ")} })[k];
  }
};
export { ${decls.map(d => d.name).join(", ")} };
`;

const outPath = process.argv[3] || "cinemeter-logic.mjs";
writeFileSync(outPath, header + body + footer);
writeFileSync(outPath.replace(/\.mjs$/, "") + "-map.txt", decls.map(d => `${d.name.padEnd(26)} line ${d.line}`).join("\n") + "\n");
console.log(`extracted ${decls.length} declarations (${letNames.length} state vars) from ${htmlPath}`);
