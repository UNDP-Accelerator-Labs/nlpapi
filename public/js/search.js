// @ts-check

import { getElement, isLoading } from './util.js';

/**
 * @typedef {{
 *  doc_count: number;
 *  fields: { [key: string]: { [key: string]: number } };
 * }} StatResult
 */

/**
 * @typedef {{
 *   hits: {
 *     base: string;
 *     doc_id: number;
 *     main_id: string;
 *     meta: {
 *       date: string;
 *       doc_type: string;
 *       iso3?: string[];
 *       language?: string[];
 *       status: string;
 *     };
 *     score: number;
 *     snippets: string[];
 *     url: string;
 *   }[];
 *   status: string;
 * }} SearchResult
 */

const BASE = window.location.host.startsWith('localhost')
  ? 'https://acclabs-nlpapi.azurewebsites.net/'
  : '';

const PAGE_SIZE = 10;
const DISPLAY_PAGE_COUNT = 10;
const MID_PAGE = Math.floor(DISPLAY_PAGE_COUNT / 2);

export default class Search {
  constructor(
    /** @type {string} */ filterId,
    /** @type {string} */ searchId,
    /** @type {string} */ resultsId,
    /** @type {string} */ paginationId,
    /** @type {string} */ docCountId,
  ) {
    /** @type {HTMLDivElement} */ this._filterDiv = getElement(filterId);
    /** @type {HTMLInputElement} */ this._searchInput = getElement(searchId);
    /** @type {HTMLDivElement} */ this._resultsDiv = getElement(resultsId);
    /** @type {HTMLDivElement} */ this._paginationDiv =
      getElement(paginationId);
    /** @type {HTMLDivElement} */ this._docCountDiv = getElement(docCountId);
    /** @type {string} */ this._input = '';
    /** @type {{ [key: string]: string[] }} */ this._filter = {};
    /** @type {{ [key: string]: boolean }} */ this._groups = {};
    /** @type {number} */ this._page = 0;
    /** @type {number} */ this._searchId = 0;
    /** @type {number} */ this._statsId = 0;
    /** @type {number} */ this._docCount = 0;

    this.setupInput();
  }

  setupInput() {
    const searchInput = this._searchInput;
    searchInput.addEventListener('keydown', (e) => {
      if (e.defaultPrevented) {
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        if (searchInput.value === this._input) {
          return;
        }
        this._input = searchInput.value;
        this._page = 0;
        this.updateSearch();
      }
    });
  }

  /** @type {() => Promise<StatResult>} */
  async getStats() {
    try {
      const res = await fetch(`${BASE}/api/stats`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ filters: this._filter }),
      });
      return await res.json();
    } catch (err) {
      console.error(err);
      return {
        doc_count: -1,
        fields: {},
      };
    }
  }

  /** @type {() => Promise<SearchResult>} */
  async getSearch() {
    try {
      const res = await fetch(`${BASE}/api/search`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input: this._input,
          filters: this._filter,
          offset: this._page * PAGE_SIZE,
          limit: PAGE_SIZE,
        }),
      });
      return await res.json();
    } catch (err) {
      console.error(err);
      return {
        hits: [],
        status: 'error',
      };
    }
  }

  updateStats() {
    console.log('update stats');
    isLoading(this._filterDiv, true);
    this._statsId += 1;
    const statsId = this._statsId;
    setTimeout(async () => {
      await this.doUpdateStats(statsId);
    }, 0);
  }

  setPageDiv() {
    const docCount = this._docCount;
    const currentPage = this._page;
    const paginationDiv = this._paginationDiv;
    const pageCount = Math.min(
      Math.ceil(docCount / PAGE_SIZE),
      DISPLAY_PAGE_COUNT + 1,
    );
    const pagination = [...Array(pageCount).keys()]
      .map((page) => ({
        page: currentPage > MID_PAGE ? page + currentPage - MID_PAGE : page,
        isFirst: page === 0,
        isLast: page >= DISPLAY_PAGE_COUNT,
      }))
      .map(({ page, isFirst, isLast }) => {
        const span = document.createElement('span');
        if (currentPage > MID_PAGE) {
          span.innerText = isFirst || isLast ? '...' : `${page}`;
        } else {
          span.innerText = isLast ? '...' : `${page}`;
        }
        if (page === currentPage) {
          span.classList.add('current');
        } else if (isLast || (currentPage > MID_PAGE && isFirst)) {
          span.classList.add('dotdotdot');
        } else {
          span.addEventListener('click', () => {
            this._page = page;
            this.setPageDiv();
            this.updateSearch();
          });
        }
        return span;
      });
    paginationDiv.replaceChildren(...pagination);
  }

  async doUpdateStats(/** @type {number} */ statsId) {
    const stats = await this.getStats();
    if (statsId !== this._statsId) {
      return;
    }
    const filterDiv = this._filterDiv;
    isLoading(filterDiv, false);
    if (stats.doc_count < 0) {
      const errDiv = document.createElement('div');
      errDiv.classList.add('error');
      errDiv.innerText = 'An error occurred! Click here to try again.';
      errDiv.addEventListener('click', () => {
        this.updateStats();
      });
      filterDiv.replaceChildren(...[errDiv]);
      return;
    }
    const groups = this._groups;
    const filter = this._filter;
    this._docCountDiv.innerText = `Total documents: ${stats.doc_count}`;
    this._docCount = stats.doc_count;
    this.setPageDiv();
    const fields = stats.fields;
    const newChildren = Object.keys(fields)
      .filter((field) => !['date', 'base'].includes(field))
      .map((field) => {
        const ul = document.createElement('ul');
        const div = document.createElement('div');
        const fieldName = document.createElement('div');
        fieldName.innerText = `${field}`;
        fieldName.classList.add('fieldName');
        if (groups[field]) {
          fieldName.classList.add('groupSelected');
          ul.classList.add('groupSelected');
        }
        fieldName.addEventListener('click', () => {
          if (groups[field]) {
            fieldName.classList.remove('groupSelected');
            ul.classList.remove('groupSelected');
            groups[field] = false;
          } else {
            fieldName.classList.add('groupSelected');
            ul.classList.add('groupSelected');
            groups[field] = true;
          }
        });
        div.appendChild(fieldName);
        const fieldVals = fields[field];
        const lis = Object.keys(fieldVals)
          .filter((value) => fieldVals[value])
          .map((value) => {
            const fieldValue = document.createElement('li');
            const isSelected = filter[field]?.includes(value);
            if (isSelected) {
              fieldValue.classList.add('fieldSelected');
            }
            fieldValue.innerText = `${value} (${fieldVals[value]})`;
            fieldValue.addEventListener('click', () => {
              if (isSelected) {
                filter[field] = filter[field].filter((f) => f !== value);
              } else {
                filter[field] = [...(filter[field] ?? []), value];
              }
              this._page = 0;
              this.updateStats();
              this.updateSearch();
            });
            return fieldValue;
          });
        ul.replaceChildren(...lis);
        div.appendChild(ul);
        return div;
      });
    filterDiv.replaceChildren(...newChildren);
  }

  updateSearch() {
    console.log('update search');
    isLoading(this._resultsDiv, true);
    this._searchId += 1;
    const searchId = this._searchId;
    setTimeout(async () => {
      await this.doUpdateSearch(searchId);
    }, 0);
  }

  async doUpdateSearch(/** @type {number} */ searchId) {
    const results = await this.getSearch();
    if (searchId !== this._searchId) {
      return;
    }
    const resultsDiv = this._resultsDiv;
    isLoading(resultsDiv, false);
    this.setPageDiv();
    if (results.status !== 'ok') {
      const errDiv = document.createElement('div');
      errDiv.classList.add('error');
      errDiv.innerText = 'An error occurred! Click here to try again.';
      errDiv.addEventListener('click', () => {
        this.updateSearch();
      });
      resultsDiv.replaceChildren(...[errDiv]);
      return;
    }
    const newChildren = results.hits.map((hit) => {
      const div = document.createElement('div');
      div.classList.add('hit');
      const link = document.createElement('a');
      link.href = hit.url;
      link.innerText = hit.url;
      div.appendChild(link);
      const info = document.createElement('div');
      info.classList.add('hitInfo');
      const docId = `${hit.base}-${hit.doc_id}`;
      const score = `score: ${hit.score}`;
      const date = `date: ${hit.meta.date}`;
      info.innerText = `${docId} ${score} ${date}`;
      div.appendChild(info);
      const demographic = document.createElement('div');
      const countries = `countries: ${(hit.meta?.iso3 ?? []).join(', ')}`;
      const languages = `languages: ${(hit.meta?.language ?? []).join(', ')}`;
      demographic.innerText = `${countries} ${languages}`;
      div.appendChild(demographic);
      const snippets = document.createElement('div');
      const snippetDivs = hit.snippets.map((snippet) => {
        const snippetDiv = document.createElement('div');
        snippetDiv.classList.add('hitSnippet');
        snippetDiv.innerText = snippet;
        return snippetDiv;
      });
      snippets.replaceChildren(...snippetDivs);
      div.appendChild(snippets);
      return div;
    });
    resultsDiv.replaceChildren(...newChildren);
  }
} // Search
