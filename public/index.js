// @ts-check

import Search from './js/search.js';

const run = async () => {
  const search = new Search(
    '#filter',
    '#search',
    '#results',
    '#pagination',
    '#docCount',
  );
  await search.updateStats();
  await search.updateSearch();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', run);
} else {
  await run();
}
