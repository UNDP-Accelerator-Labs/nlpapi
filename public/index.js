// @ts-check

import Search from './js/search.js';

const LIVE_API = 'https://nlpapi.sdg-innovation-commons.org/';

const start = (/** @type {string} */ base) => {
  const search = new Search(
    '#filter',
    '#search',
    '#results',
    '#pagination',
    '#docCount',
    ['doc_type', 'iso3', 'language', 'status'],
    base,
  );
  search.updateStats(null);
  search.updateSearch();
};

const run = async () => {
  try {
    const versionResponse = await fetch('/api/version');
    const versionObj = await versionResponse.json();
    if (versionObj.error) {
      start(LIVE_API);
    } else {
      start('');
    }
  } catch (_) {
    start(LIVE_API);
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', run);
} else {
  await run();
}
