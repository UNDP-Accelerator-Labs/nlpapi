// @ts-check

import { getElement, setLoading } from './util.js';

/**
 * @typedef {{
 *  doc_count: number;
 *  fields: { [key: string]: { [key: string]: number } };
 * }} StatResult
 */

/**
 * @typedef {{
 *  doc_count: number?;
 *  fields: { [key: string]: { [key: string]: number? } };
 * }} StatResultCache
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
 *     title: string;
 *   }[];
 *   status: string;
 * }} SearchResult
 */

/**
 * @typedef {{
 *   q: string;
 *   filter: string;
 *   p: number;
 * }} SearchState
 */

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
    /** @type {string[]} */ fields,
    /** @type {string} */ base,
  ) {
    /** @type {HTMLDivElement} */ this._filterDiv = getElement(filterId);
    /** @type {HTMLInputElement} */ this._searchInput = getElement(searchId);
    /** @type {HTMLDivElement} */ this._resultsDiv = getElement(resultsId);
    /** @type {HTMLDivElement} */ this._paginationDiv =
      getElement(paginationId);
    /** @type {HTMLDivElement} */ this._docCountDiv = getElement(docCountId);
    /** @type {{ [key: string]: HTMLUListElement }} */ this._groupElems = {};
    /** @type {string[]} */ this._allFields = fields;
    /** @type {string} */ this._base = base;
    /** @type {string} */ this._input = '';
    /** @type {{ [key: string]: string[] }} */ this._filter = {};
    /** @type {{ [key: string]: boolean }} */ this._groups = {};
    /** @type {number} */ this._page = 0;
    /** @type {number} */ this._searchId = 0;
    /** @type {number} */ this._statsId = 0;
    /** @type {number} */ this._docCount = 0;
    /** @type {StatResultCache} */ this._statCache = {
      doc_count: null,
      fields: {},
    };
    /** @type {SearchState} */ this._state = {
      q: this._input,
      filter: this.getFiltersString(),
      p: this._page,
    };
    window.addEventListener('popstate', (event) => {
      /** @type {SearchState} */ const state = event.state;
      const { q, filter, p } = state;
      if (q && filter && p) {
        this._input = q;
        this._filter = JSON.parse(filter);
        this._page = p;
        this._state = { q, filter, p };
        this._searchInput.value = this._input;
        this.updateStats(null);
        this.updateSearch();
      }
    });

    this.getFromParams();
    this.setupInput();
  }

  getFromParams() {
    const params = new URL(window.location.href).searchParams;
    const query = params.get('q');
    if (query) {
      this._input = query;
    }
    const filters = params.get('filters');
    try {
      if (filters) {
        const filtersObj = JSON.parse(filters);
        this._filter = filtersObj;
      }
    } catch (_) {
      // nop
    }
    const page = params.get('p');
    if (page !== undefined && page !== null) {
      const pageNum = +page;
      if (Number.isFinite(pageNum)) {
        this._page = pageNum;
      }
    }
    this._state = {
      q: this._input,
      filter: this.getFiltersString(),
      p: this._page,
    };
    this._searchInput.value = this._input;
  }

  getFiltersString() {
    const filter = this._filter;
    return JSON.stringify(filter, Object.keys(filter).sort());
  }

  pushHistory() {
    const { q: oldQ, filter: oldFilter, p: oldP } = this._state;
    const q = this._input;
    const filter = this.getFiltersString();
    const p = this._page;
    if (q !== oldQ || filter !== oldFilter || p !== oldP) {
      const history = window.history;
      const params = new URLSearchParams();
      params.set('q', q);
      params.set('filter', filter);
      params.set('p', `${p}`);
      const url = new URL(window.location.href);
      url.search = params.toString();
      history.pushState({ q, filter, p }, '', url);
    }
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

  /** @type {(fields: string[]) => Promise<StatResult>} */
  async getStats(fields) {
    try {
      const res = await fetch(`${this._base}/api/stats`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ fields, filters: this._filter }),
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
      const res = await fetch(`${this._base}/api/search`, {
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
          short_snippets: true,
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

  renderStats() {
    const stats = this._statCache;
    const filterDiv = this._filterDiv;
    if (stats.doc_count !== null && stats.doc_count < 0) {
      const errDiv = document.createElement('div');
      errDiv.classList.add('error');
      errDiv.innerText = 'An error occurred! Click here to try again.';
      errDiv.addEventListener('click', () => {
        errDiv.remove();
        this.updateStats(null);
      });
      filterDiv.replaceChildren(...[errDiv]);
      this._groupElems = {};
      return;
    }
    const groups = this._groups;
    const filter = this._filter;
    if (stats.doc_count !== null) {
      this._docCountDiv.innerText = `Total documents: ${stats.doc_count}`;
      setLoading(this._docCountDiv, false);
      this._docCount = stats.doc_count;
      this.setPageDiv();
    } else {
      setLoading(this._docCountDiv, true);
    }
    const fields = stats.fields;
    Object.keys(fields)
      .filter((field) => !['date', 'base'].includes(field))
      .forEach((field) => {
        let ul = this._groupElems[field];
        if (!ul) {
          const div = document.createElement('div');
          ul = document.createElement('ul');
          const fieldName = document.createElement('div');
          fieldName.innerText = `${field}`;
          fieldName.classList.add('fieldName');
          if (groups[field]) {
            fieldName.classList.add('groupSelected');
            ul.classList.add('groupSelected');
          }
          fieldName.addEventListener('click', () => {
            const groups = this._groups;
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
          div.appendChild(ul);
          filterDiv.appendChild(div);
          this._groupElems[field] = ul;
        }
        const fieldVals = fields[field];
        const lis = Object.keys(fieldVals)
          .filter((value) => fieldVals[value] !== 0)
          .map((value) => {
            const fieldValue = document.createElement('li');
            const isSelected = filter[field]?.includes(value);
            if (isSelected) {
              fieldValue.classList.add('fieldSelected');
            }
            fieldValue.innerText =
              fieldVals[value] === null
                ? `${value}`
                : `${value} (${fieldVals[value]})`;
            fieldValue.addEventListener('click', () => {
              const filter = this._filter;
              const isSelected = filter[field]?.includes(value);
              console.log(filter[field]);
              if (isSelected) {
                filter[field] = filter[field].filter((f) => f !== value);
              } else {
                filter[field] = [...(filter[field] ?? []), value];
              }
              fieldValue.classList.toggle('fieldSelected', !isSelected);
              console.log(fieldValue, fieldValue.classList);
              this._page = 0;
              this.updateStats(field);
              this.updateSearch();
            });
            return fieldValue;
          });
        ul.replaceChildren(...lis);
      });
  }

  updateStats(/** @type {string?} */ field) {
    console.log('update stats');
    this._statsId += 1;
    const statsId = this._statsId;
    const { fields } = this._statCache;
    this._statCache = {
      doc_count: null,
      fields: Object.keys(fields).reduce((newFields, key) => {
        newFields[key] =
          key === field
            ? fields[key]
            : Object.keys(fields[key]).reduce((newValues, value) => {
                newValues[value] = fields[key][value] !== 0 ? null : 0;
                return newValues;
              }, {});
        return newFields;
      }, {}),
    };
    this.renderStats();
    setTimeout(async () => {
      await this.doUpdateStats(statsId, field);
    }, 0);
  }

  async doUpdateStats(
    /** @type {number} */ statsId,
    /** @type {string?} */ field,
  ) {
    const stats = await this.getStats(
      this._allFields.filter((f) => f !== field),
    );
    if (statsId !== this._statsId) {
      return;
    }
    this._statCache = stats;
    this.renderStats();
  }

  updateSearch() {
    console.log('update search');
    setLoading(this._resultsDiv, true);
    this._searchId += 1;
    const searchId = this._searchId;
    setTimeout(async () => {
      this.pushHistory();
      await this.doUpdateSearch(searchId);
    }, 0);
  }

  async doUpdateSearch(/** @type {number} */ searchId) {
    const results = await this.getSearch();
    if (searchId !== this._searchId) {
      return;
    }
    const resultsDiv = this._resultsDiv;
    setLoading(resultsDiv, false);
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
      link.innerText = hit.title;
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
