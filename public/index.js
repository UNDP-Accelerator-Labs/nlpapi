// @ts-check

import Search from './js/search.js';

const run = () => {
  const search = new Search(
    '#filter',
    '#search',
    '#results',
    '#pagination',
    '#docCount',
  );
  search.updateStats();
  search.updateSearch();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', run);
} else {
  run();
}
