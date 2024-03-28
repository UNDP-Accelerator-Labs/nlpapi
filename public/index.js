// @ts-check

import Search from './js/search.js';

const run = () => {
  const search = new Search(
    '#filter',
    '#search',
    '#results',
    '#pagination',
    '#docCount',
    ['doc_type', 'iso3', 'language', 'status'],
  );
  search.updateStats(null);
  search.updateSearch();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', run);
} else {
  run();
}
