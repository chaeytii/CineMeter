import { installDom, resetDom } from "./dom-stub.mjs";
import { rng } from "./dataset.mjs";
installDom();
// deterministic Math.random so pass/fail and coverage are identical on every run
Math.random = rng(2026);
// the app logs index fallbacks with console.warn — keep test output readable
const warnings = [];
console.warn = (...a) => warnings.push(a.join(" "));
export { warnings, resetDom };

const target = process.env.CINEMETER_LOGIC || "../cinemeter-logic.mjs";
export const app = await import(new URL(target, import.meta.url));

import { makeFakeDb } from "./fake-firestore.mjs";
import { makeMovies } from "./dataset.mjs";
export { makeFakeDb, makeMovies };

// Fresh app state + fake DB for a test
export async function useDb(rows, opts = {}, { genresComplete = false } = {}) {
  const extra = genresComplete ? { META: [{ id: "genres", complete: true }] } : {};
  const fdb = makeFakeDb(rows, { ...opts, extraCollections: { ...extra, ...(opts.extraCollections || {}) } });
  const h = app.__hooks;
  h.setGetDocs(fdb.getDocs);
  h.setGetDoc(fdb.getDoc);
  h.set("collectionResolved", false);
  h.set("targetCollection", "MOVIES");
  h.set("latestYear", 2026);
  h.set("votesField", null); h.set("votesNumeric", false); h.set("mediaField", null); h.set("mediaServerFilter", false);
  h.set("hasPopularityField", true); h.set("genresArrayReady", false);
  h.set("loadedMovies", []); h.set("searchQuery", ""); h.set("requestId", 0); h.set("loading", false);
  h.set("exhausted", false); h.set("lastVisibleDoc", null);
  app.brokenStrategies.clear();
  app.pageCache.clear();
  app.genreSDCache.clear();
  Object.assign(app.activeFilters, { genre: "", year: "", media: "", popular: "popular" });
  await app.detectValidCollection();
  fdb.stats.queries = 0; fdb.stats.reads = 0; fdb.stats.log.length = 0;
  return fdb;
}

export const F = (o = {}) => ({ genre: "", year: "", media: "", popular: "popular", search: "", ...o });
