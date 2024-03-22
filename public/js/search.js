// @ts-check

import { getElement } from './util.js';

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

const PAGE_SIZE = 10;

export default class Search {
  constructor(
    /** @type {string} */ filterId,
    /** @type {string} */ searchId,
    /** @type {string} */ resultsId,
    /** @type {string} */ paginationId,
  ) {
    /** @type {HTMLDivElement} */ this._filterDiv = getElement(filterId);
    /** @type {HTMLInputElement} */ this._searchInput = getElement(searchId);
    /** @type {HTMLDivElement} */ this._resultsDiv = getElement(resultsId);
    /** @type {HTMLDivElement} */ this._paginationDiv =
      getElement(paginationId);
    /** @type {string} */ this._input = '';
    /** @type {{ [key: string]: string[] }} */ this._filter = {};
    /** @type {{ [key: string]: boolean }} */ this._groups = {};
    /** @type {number} */ this._page = 0;

    this.setupInput();
  }

  setupInput() {
    const searchInput = this._searchInput;
    searchInput.addEventListener('change', () => {
      const current = searchInput.value;
      this._input = current;
      setTimeout(async () => {
        if (this._input !== current) {
          return;
        }
        await this.updateSearch();
      }, 600);
    });

    searchInput.addEventListener('blur', async () => {
      await this.updateSearch();
    });
    searchInput.addEventListener('keydown', async (e) => {
      if (e.defaultPrevented) {
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        await this.updateSearch();
      }
    });
  }

  /** @type {() => Promise<StatResult>} */
  async getStats() {
    if (window.location.host.startsWith('localhost')) return TEST_STATS;
    const res = await fetch('/api/stats', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ filters: this._filter }),
    });
    return await res.json();
  }

  /** @type {() => Promise<SearchResult>} */
  async getSearch() {
    if (window.location.host.startsWith('localhost')) return TEST_SEARCH;
    const res = await fetch('/api/search', {
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
  }

  async updateStats() {
    console.log('update stats');
    const stats = await this.getStats();
    const paginationDiv = this._paginationDiv;
    const filter = this._filter;
    const groups = this._groups;
    const docCount = document.createElement('div');
    docCount.innerText = `${stats.doc_count}`;
    paginationDiv.replaceChildren(...[docCount]);
    const filterDiv = this._filterDiv;
    const fields = stats.fields;
    const newChildren = Object.keys(fields)
      .filter((field) => !['date'].includes(field))
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
        const lis = Object.keys(fieldVals).map((value) => {
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

  async updateSearch() {
    console.log('update search');
    const results = await this.getSearch();
    const resultsDiv = this._resultsDiv;
    const newChildren = results.hits.map((hit) => {
      const div = document.createElement('div');
      const link = document.createElement('a');
      link.href = hit.url;
      link.innerText = hit.url;
      div.appendChild(link);
      return div;
    });
    resultsDiv.replaceChildren(...newChildren);
  }
} // Search

const TEST_STATS = {
  doc_count: 5248,
  fields: {
    base: {
      actionplan: 1234,
      experiment: 260,
      solution: 3754,
    },
    date: {
      '2021-04-04': 1,
      '2021-04-06': 6,
      '2021-04-07': 23,
      '2021-04-08': 15,
      '2021-04-09': 1,
      '2021-04-13': 7,
      '2021-04-14': 1,
      '2021-04-15': 2,
      '2021-04-16': 1,
      '2021-05-11': 2,
      '2021-05-12': 1,
      '2021-05-25': 1,
      '2021-05-31': 1,
      '2021-06-04': 1,
      '2021-06-07': 1,
      '2021-06-10': 1,
      '2021-08-10': 1,
      '2021-08-17': 1,
      '2021-08-18': 1,
      '2021-08-24': 1,
      '2021-09-14': 1,
      '2021-09-30': 1,
      '2021-10-06': 3,
      '2021-10-08': 1,
      '2021-10-13': 2,
      '2021-10-14': 2,
      '2021-10-25': 1,
      '2021-10-28': 2,
      '2021-11-01': 2,
      '2021-11-02': 2,
      '2021-11-03': 2,
      '2021-11-06': 1,
      '2021-11-12': 1,
      '2021-11-15': 3,
      '2021-11-19': 2,
      '2021-11-23': 1,
      '2021-11-25': 1,
      '2021-11-30': 2,
      '2021-12-01': 2,
      '2021-12-31': 1,
      '2022-01-05': 1,
      '2022-01-06': 1,
      '2022-01-20': 2,
      '2022-01-24': 1,
      '2022-01-25': 4,
      '2022-01-26': 3,
      '2022-01-28': 2,
      '2022-01-31': 5,
      '2022-02-01': 4,
      '2022-02-02': 11,
      '2022-02-03': 13,
      '2022-02-04': 26,
      '2022-02-05': 6,
      '2022-02-06': 4,
      '2022-02-07': 6,
      '2022-02-08': 3,
      '2022-02-10': 6,
      '2022-02-11': 17,
      '2022-02-13': 3,
      '2022-02-14': 3,
      '2022-02-18': 1,
      '2022-02-21': 1,
      '2022-02-22': 1,
      '2022-02-23': 4,
      '2022-02-24': 1,
      '2022-02-27': 1,
      '2022-03-02': 1,
      '2022-03-04': 1,
      '2022-03-08': 3,
      '2022-03-09': 3,
      '2022-03-10': 3,
      '2022-03-13': 1,
      '2022-03-14': 6,
      '2022-03-15': 16,
      '2022-03-16': 9,
      '2022-03-17': 4,
      '2022-03-23': 1,
      '2022-03-24': 2,
      '2022-03-25': 1,
      '2022-03-27': 1,
      '2022-03-28': 1,
      '2022-04-05': 3,
      '2022-04-06': 2,
      '2022-04-07': 1,
      '2022-04-11': 3,
      '2022-04-12': 7,
      '2022-04-14': 5,
      '2022-04-18': 2,
      '2022-04-19': 4,
      '2022-04-20': 2,
      '2022-04-21': 4,
      '2022-04-22': 1,
      '2022-04-24': 1,
      '2022-04-26': 6,
      '2022-04-27': 5,
      '2022-04-28': 6,
      '2022-04-29': 10,
      '2022-04-30': 12,
      '2022-05-01': 3,
      '2022-05-02': 1,
      '2022-05-03': 3,
      '2022-05-04': 3,
      '2022-05-05': 13,
      '2022-05-07': 4,
      '2022-05-09': 2,
      '2022-05-10': 3,
      '2022-05-13': 1,
      '2022-05-16': 1,
      '2022-05-17': 3,
      '2022-05-18': 1,
      '2022-05-20': 1,
      '2022-05-23': 1,
      '2022-05-25': 2,
      '2022-05-26': 1,
      '2022-05-31': 1,
      '2022-06-02': 2,
      '2022-06-03': 2,
      '2022-06-06': 3,
      '2022-06-08': 1,
      '2022-06-09': 3,
      '2022-06-10': 1,
      '2022-06-14': 5,
      '2022-06-15': 1,
      '2022-06-22': 1,
      '2022-06-30': 3,
      '2022-07-01': 1,
      '2022-07-05': 1,
      '2022-07-27': 1,
      '2022-08-01': 1,
      '2022-08-03': 1,
      '2022-08-04': 2,
      '2022-08-05': 1,
      '2022-08-08': 1,
      '2022-08-11': 5,
      '2022-08-12': 4,
      '2022-08-16': 6,
      '2022-08-22': 1,
      '2022-08-23': 8,
      '2022-08-24': 22,
      '2022-08-26': 4,
      '2022-08-29': 2,
      '2022-08-30': 1,
      '2022-08-31': 2,
      '2022-09-02': 22,
      '2022-09-07': 2,
      '2022-09-14': 3,
      '2022-09-21': 2,
      '2022-09-27': 1,
      '2022-10-06': 1,
      '2022-10-10': 8,
      '2022-10-19': 3,
      '2022-10-22': 1,
      '2022-10-24': 3,
      '2022-10-26': 1,
      '2022-10-27': 5,
      '2022-11-01': 1,
      '2022-11-03': 1,
      '2022-11-04': 1,
      '2022-11-09': 7,
      '2022-11-10': 1,
      '2022-11-28': 1,
      '2022-11-30': 3,
      '2022-12-05': 2,
      '2022-12-08': 1,
      '2022-12-19': 7,
      '2022-12-20': 2,
      '2022-12-21': 3,
      '2022-12-22': 4,
      '2022-12-23': 1,
      '2022-12-24': 1,
      '2022-12-26': 3,
      '2022-12-27': 1,
      '2022-12-28': 1,
      '2022-12-29': 2,
      '2022-12-30': 2,
      '2022-12-31': 5,
      '2023-01-03': 3,
      '2023-01-04': 7,
      '2023-01-05': 3,
      '2023-01-08': 1,
      '2023-01-09': 1,
      '2023-01-10': 1,
      '2023-01-11': 1,
      '2023-01-12': 1,
      '2023-01-15': 1,
      '2023-01-16': 2911,
      '2023-01-19': 12,
      '2023-01-20': 19,
      '2023-01-21': 1,
      '2023-01-23': 56,
      '2023-01-24': 66,
      '2023-01-25': 6,
      '2023-01-26': 22,
      '2023-01-27': 3,
      '2023-01-29': 1,
      '2023-01-30': 19,
      '2023-01-31': 48,
      '2023-02-01': 18,
      '2023-02-02': 32,
      '2023-02-03': 6,
      '2023-02-04': 4,
      '2023-02-06': 1,
      '2023-02-07': 15,
      '2023-02-08': 1,
      '2023-02-09': 3,
      '2023-02-12': 1,
      '2023-02-13': 1,
      '2023-02-14': 7,
      '2023-02-15': 1,
      '2023-02-21': 9,
      '2023-02-22': 4,
      '2023-02-23': 8,
      '2023-02-24': 2,
      '2023-02-26': 1,
      '2023-02-27': 12,
      '2023-02-28': 2,
      '2023-03-01': 1,
      '2023-03-05': 1,
      '2023-03-06': 1,
      '2023-03-16': 7,
      '2023-03-17': 3,
      '2023-03-20': 1,
      '2023-03-21': 1,
      '2023-03-22': 6,
      '2023-03-23': 5,
      '2023-03-24': 1,
      '2023-03-29': 2,
      '2023-04-04': 1,
      '2023-04-11': 2,
      '2023-04-13': 1,
      '2023-04-17': 5,
      '2023-04-18': 1,
      '2023-04-19': 5,
      '2023-04-20': 2,
      '2023-04-27': 1,
      '2023-04-28': 3,
      '2023-05-04': 5,
      '2023-05-12': 18,
      '2023-05-15': 1,
      '2023-05-16': 8,
      '2023-05-18': 17,
      '2023-05-19': 88,
      '2023-05-22': 1,
      '2023-05-23': 10,
      '2023-05-24': 17,
      '2023-05-29': 1,
      '2023-05-30': 4,
      '2023-05-31': 3,
      '2023-06-01': 1,
      '2023-06-05': 49,
      '2023-06-08': 1,
      '2023-06-09': 1,
      '2023-06-12': 1,
      '2023-06-13': 4,
      '2023-06-21': 3,
      '2023-06-28': 1,
      '2023-06-30': 1,
      '2023-07-10': 20,
      '2023-07-11': 3,
      '2023-07-12': 24,
      '2023-07-13': 2,
      '2023-07-14': 1,
      '2023-07-17': 15,
      '2023-07-18': 6,
      '2023-07-19': 4,
      '2023-07-20': 4,
      '2023-07-25': 34,
      '2023-07-26': 2,
      '2023-07-27': 3,
      '2023-07-28': 7,
      '2023-07-31': 6,
      '2023-08-02': 2,
      '2023-08-03': 1,
      '2023-08-04': 1,
      '2023-08-08': 1,
      '2023-08-09': 17,
      '2023-08-10': 7,
      '2023-08-11': 1,
      '2023-08-13': 6,
      '2023-08-14': 3,
      '2023-08-15': 4,
      '2023-08-16': 3,
      '2023-08-17': 4,
      '2023-08-18': 2,
      '2023-08-19': 1,
      '2023-08-22': 3,
      '2023-08-23': 9,
      '2023-08-24': 11,
      '2023-08-25': 12,
      '2023-08-27': 1,
      '2023-08-28': 6,
      '2023-08-29': 1,
      '2023-08-30': 1,
      '2023-08-31': 1,
      '2023-09-01': 1,
      '2023-09-04': 15,
      '2023-09-05': 2,
      '2023-09-06': 8,
      '2023-09-07': 9,
      '2023-09-08': 2,
      '2023-09-12': 17,
      '2023-09-13': 4,
      '2023-09-14': 1,
      '2023-09-15': 1,
      '2023-09-18': 1,
      '2023-09-19': 5,
      '2023-09-21': 1,
      '2023-10-03': 1,
      '2023-10-06': 1,
      '2023-10-10': 1,
      '2023-10-11': 1,
      '2023-10-13': 1,
      '2023-10-17': 1,
      '2023-10-19': 2,
      '2023-10-20': 1,
      '2023-10-25': 1,
      '2023-10-26': 3,
      '2023-10-31': 2,
      '2023-11-01': 46,
      '2023-11-06': 2,
      '2023-11-07': 4,
      '2023-11-08': 4,
      '2023-11-09': 1,
      '2023-11-10': 4,
      '2023-11-16': 3,
      '2023-11-21': 3,
      '2023-11-23': 1,
      '2023-11-24': 1,
      '2023-11-29': 4,
      '2023-12-01': 1,
      '2023-12-03': 1,
      '2023-12-05': 4,
      '2023-12-06': 2,
      '2023-12-07': 2,
      '2023-12-08': 11,
      '2023-12-09': 1,
      '2023-12-11': 9,
      '2023-12-12': 5,
      '2023-12-13': 24,
      '2023-12-14': 11,
      '2023-12-15': 252,
      '2023-12-16': 2,
      '2023-12-17': 4,
      '2023-12-18': 9,
      '2023-12-19': 13,
      '2023-12-20': 18,
      '2023-12-21': 16,
      '2023-12-22': 47,
      '2023-12-23': 4,
      '2023-12-25': 2,
      '2023-12-26': 6,
      '2023-12-27': 6,
      '2023-12-28': 4,
      '2023-12-29': 4,
      '2024-01-01': 1,
      '2024-01-08': 6,
      '2024-01-09': 3,
      '2024-01-10': 12,
      '2024-01-11': 9,
      '2024-01-12': 7,
      '2024-01-13': 4,
      '2024-01-14': 5,
      '2024-01-15': 1,
      '2024-01-16': 8,
      '2024-01-18': 1,
      '2024-01-19': 5,
      '2024-01-22': 1,
      '2024-01-23': 3,
      '2024-01-25': 12,
      '2024-01-26': 7,
      '2024-01-29': 1,
      '2024-01-30': 8,
      '2024-01-31': 15,
      '2024-02-01': 6,
      '2024-02-04': 10,
      '2024-02-05': 3,
      '2024-02-06': 1,
      '2024-02-07': 2,
      '2024-02-08': 3,
      '2024-02-12': 1,
      '2024-02-14': 1,
      '2024-02-15': 2,
      '2024-02-16': 2,
      '2024-02-19': 1,
      '2024-02-20': 3,
      '2024-02-21': 4,
      '2024-02-22': 1,
      '2024-02-23': 1,
      '2024-02-26': 2,
      '2024-02-27': 2,
      '2024-02-28': 3,
      '2024-02-29': 3,
      '2024-03-01': 10,
      '2024-03-04': 4,
      '2024-03-05': 2,
      '2024-03-06': 3,
      '2024-03-07': 10,
      '2024-03-08': 4,
      '2024-03-11': 2,
      '2024-03-13': 8,
      '2024-03-14': 2,
      '2024-03-15': 3,
      '2024-03-18': 2,
      '2024-03-19': 5,
      '2024-03-20': 3,
      '2024-03-21': 1,
    },
    doc_type: {
      'action plan': 1234,
      experiment: 260,
      solution: 3754,
    },
    iso3: {
      ABW: 2,
      AFG: 6,
      AGO: 28,
      ALB: 8,
      ARE: 1,
      ARG: 81,
      AUS: 35,
      AUT: 32,
      AZE: 6,
      BDI: 3,
      BEL: 4,
      BEN: 16,
      BFA: 13,
      BGD: 104,
      BGR: 6,
      BHR: 1,
      BIH: 19,
      BLR: 22,
      BLZ: 1,
      BOL: 21,
      BRA: 53,
      BRB: 25,
      BTN: 12,
      BWA: 7,
      CAF: 1,
      CAN: 60,
      CHE: 19,
      CHL: 15,
      CHN: 26,
      CIV: 5,
      CMR: 26,
      COD: 25,
      COK: 3,
      COL: 52,
      COM: 1,
      CPV: 15,
      CRI: 11,
      CUB: 8,
      CUW: 3,
      CYP: 1,
      CZE: 4,
      DEU: 300,
      DMA: 8,
      DNK: 12,
      DOM: 15,
      DZA: 11,
      ECU: 52,
      EGY: 33,
      ESP: 97,
      EST: 1,
      ETH: 42,
      FIN: 7,
      FJI: 57,
      FLK: 2,
      FRA: 96,
      GBR: 80,
      GEO: 31,
      GHA: 17,
      GIN: 38,
      GMB: 2,
      GNB: 28,
      GNQ: 3,
      GRC: 9,
      GRD: 7,
      GRL: 2,
      GTM: 54,
      GUY: 2,
      HKG: 6,
      HND: 9,
      HRV: 9,
      HTI: 13,
      HUN: 2,
      IDN: 46,
      IND: 118,
      IOT: 1,
      IRL: 9,
      IRN: 14,
      IRQ: 43,
      ISL: 12,
      ISR: 11,
      ITA: 63,
      JAM: 1,
      JOR: 55,
      JPN: 36,
      KAZ: 17,
      KEN: 37,
      KGZ: 15,
      KHM: 21,
      KIR: 1,
      KOR: 6,
      KWT: 9,
      LAO: 16,
      LBN: 15,
      LBR: 1,
      LBY: 15,
      LCA: 3,
      LSO: 7,
      LTU: 3,
      LUX: 2,
      LVA: 2,
      MAF: 1,
      MAR: 12,
      MDA: 2,
      MDG: 4,
      MDV: 17,
      MEX: 76,
      MHL: 1,
      MKD: 46,
      MLI: 11,
      MMR: 8,
      MNG: 15,
      MOZ: 12,
      MRT: 18,
      MUS: 8,
      MWI: 12,
      MYS: 63,
      NAM: 18,
      NER: 6,
      NGA: 25,
      NIC: 4,
      NIU: 1,
      NLD: 28,
      NOR: 4,
      NPL: 18,
      NRU: 1,
      NUL: 99,
      NZL: 13,
      OMN: 3,
      PAK: 6,
      PAN: 40,
      PER: 23,
      PHL: 52,
      PNG: 4,
      POL: 9,
      PRI: 11,
      PRT: 18,
      PRY: 11,
      PSE: 5,
      QAT: 3,
      ROU: 12,
      RUS: 36,
      RWA: 19,
      SAU: 11,
      SDN: 13,
      SEN: 13,
      SGP: 25,
      SLB: 1,
      SLE: 3,
      SLV: 23,
      SOM: 12,
      SRB: 53,
      SSD: 6,
      SUR: 2,
      SVK: 2,
      SVN: 1,
      SWE: 20,
      SWZ: 6,
      SYC: 9,
      SYR: 30,
      TCD: 6,
      TGO: 4,
      THA: 32,
      TJK: 1,
      TKL: 3,
      TKM: 2,
      TLS: 11,
      TON: 3,
      TTO: 18,
      TUN: 8,
      TUR: 34,
      TUV: 5,
      TWN: 2,
      TZA: 55,
      UGA: 60,
      UKR: 45,
      URY: 22,
      USA: 667,
      UZB: 29,
      VEN: 19,
      VGB: 3,
      VNM: 24,
      VUT: 13,
      WSM: 4,
      YEM: 10,
      ZAF: 64,
      ZMB: 34,
      ZWE: 18,
    },
    language: {
      af: 5,
      ca: 8,
      cy: 1,
      da: 2,
      de: 8,
      en: 4813,
      es: 380,
      fi: 2,
      fr: 248,
      hr: 1,
      id: 2,
      it: 18,
      nl: 6,
      no: 3,
      pt: 1,
      ro: 7,
      sv: 3,
      tl: 3,
      tr: 3,
    },
    status: {
      preview: 3840,
      public: 1408,
    },
  },
};

const TEST_SEARCH = {
  hits: [
    {
      base: 'actionplan',
      doc_id: 1665,
      main_id: 'actionplan:1665',
      meta: {
        date: '2023-09-06T16:13:13.022073+00:00',
        doc_type: 'action plan',
        iso3: ['ARG', 'CAN', 'DEU', 'FRA', 'USA'],
        language: ['en'],
        status: 'public',
      },
      score: 0.6301813,
      snippets: [
        'question?\nArtificial intelligence is at the heart of our efforts to identify patterns and commonalities in the opening speeches of different presidents across political parties. This exercise not only serves as a proof of concept but also provides a prototype for testing the potential of AI to support democratic governance. We will leverage collective intelligence to identify past and future plans for AI and work towards regulating this field to balance its possibilities and risks. \nBy harnessing the power of AI, we can more effectively analyze and understand the nuances of',
        's of political discourse, leading to more informed decision-making. However, we must also recognize and address the potential risks that come with this technology, such as bias or lack of transparency. Through collaboration and regulation, we can ensure that AI serves the public good and contributes to a more transparent and inclusive democracy.\nNew sources of data: What types of new data sources are you using for this learning question?\ndatasources: artificial intelligence data\nExisting data gaps: Relating to your choice above, what existing gaps in data or information do these new',
        'of techniques and algorithms that allow machines to learn from experience and make decisions based on data and patterns. In simple terms, AI is an intelligent system that can perform tasks that would normally require human intervention. In the context of democracy, this can be a powerful tool for improving transparency, citizen participation, and decision-making. \nIn Argentina, the government is leading the conversation on this issue. The UNDP is also adopting tools mainly to counterbalance disinformation. For instance, it uses EMonitor+, an AI-powered tool to promote access to',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=1665',
    },
    {
      base: 'actionplan',
      doc_id: 2030,
      main_id: 'actionplan:2030',
      meta: {
        date: '2023-12-21T19:08:21.556161+00:00',
        doc_type: 'action plan',
        iso3: ['ALB', 'ARG', 'CAN', 'CHE', 'PNG', 'RUS', 'USA'],
        language: ['en', 'es', 'fr'],
        status: 'public',
      },
      score: 0.61269355,
      snippets: [
        'l media, blogs), is allowing us to explore analytics dimensions, variables and indicators that could be helpful to try to make sense of the interaction between AI and democracy. Moreover, by testing an AI tool for politics speech analysis and generation, we hope to create evidence of the possibilities and shortcomings of this technology in relation to democracy. Moreover, our work has a formative effect on the national and regional AI ecosystem. At the same time we are making efforts for studying the AI ecosystem, we are contributing to its formation. By highlighting experts,',
        'e used for analyzing common values across different presidents and periods of time. Additionally, we are developing others knowledge products related to employment in the era of AI, and regulations on AI. \nWe hope to engage in conversations with further private partners, and civil society organizations to promote a greater reach of our actions regarding AI. Furthermore, we plan to approach the newly elected national authorities to share our work, hoping to engage them in our challenge.\nPlease paste any link(s) to blog(s) or publication(s) that articulate the learnings on your',
        "s strategic priorities for integrating AI with its development. From the government's perspective, conversation about AI is not a priority. There have been few efforts in terms of strategy and regulation, and what little has been done lacks continuity between one government and the next. \n- Geopolitical concerns: There are specific geopolitical concerns in relation to the development of AI; for instance, there are fears that the increasing competition between global powers will trigger a process of technological nationalism. As it happened during the Cold War, barriers to the free",
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=2030',
    },
    {
      base: 'actionplan',
      doc_id: 1780,
      main_id: 'actionplan:1780',
      meta: {
        date: '2023-09-12T21:26:21.646037+00:00',
        doc_type: 'action plan',
        iso3: ['CHE', 'VNM'],
        language: ['en'],
        status: 'public',
      },
      score: 0.50047415,
      snippets: [
        "\u201d summary: We would like to tweet what you are working on, can you summarize your challenge in a maximum of 280 characters?\n\ud83e\udd16 Exploring how AI impacts job skills in Vietnam. As automation rises, what skills will be vital for future jobs? We're uncovering insights and strategies to bridge the skill gap and empower the Vietnamese workforce! #AIJobsVietnam\nChallenge classification\nTaxonomy: To which topic-clusters does this challenge belong? (please choose up to 3)\nthematic_areas: youth and unemployment\nthematic_areas: youth empowerment\nthematic_areas: artificial",
        'artificial intelligence\nthematic_areas: futures\nSDGs: What SDGs is your challenge related to? (please choose the top 3)\nsdgs: Quality education\nsdgs: Decent work and economic growth\nsdgs: Industry, innovation and infrastructure\nPartners\nPlease state the name of the partner:\nHanoi University of Science and Technology\nNational Economics University\nUN agencies (ILO, UNICEF, UNESCO...)\nWhat sector does our partner belong to?\nUnited Nations\nPlease provide a brief description of the collaboration.\nThis is part of UNDP CO effort to position itself in the Youth participation space and',
        'question relate?\nSense\nExplore\nInnovation methods: What are your top 5 key innovation methods or tools that you are planning to use for this learning question?\nmethods: Horizon Scanning\nmethods: Future Analysis\nmethods: Foresight\nmethods: Data Visualisation\nmethods: Artificial Intelligence/Machine Learning\nUsage of methods: Relating to your choice above, how will you use your methods & tools for this learning question? What value do these add in answering your learning question?\nFuture Analysis: Identify emerging AI-driven job roles and required skills.\nScenario Planning: Develop',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=1780',
    },
    {
      base: 'actionplan',
      doc_id: 1523,
      main_id: 'actionplan:1523',
      meta: {
        date: '2023-08-09T11:15:40.745598+00:00',
        doc_type: 'action plan',
        iso3: ['CPV', 'CRI', 'ITA', 'USA'],
        language: ['en'],
        status: 'public',
      },
      score: 0.49998558,
      snippets: [
        'the feasibility of using new technologies such as technologies such as the Internet of Things (IoT) and Artificial Intelligence (AI) to improve the efficiency and productivity of and efficiency of agricultural production. Specifically, this project will use sensor networks to wirelessly to monitor soil, weather conditions, water availability for irrigation, and drones to monitor crop growth, and based on the data collected, we will combine artificial intelligence models to define strategies to increase production. To validate our hypothesis, we will carry out a pilot project in',
        'artificial intelligence\nthematic_areas: climate change\nthematic_areas: food security\nthematic_areas: digital data collection\nthematic_areas: agri-food resilience\nthematic_areas: data\nthematic_areas: digital solution\nthematic_areas: drones\nSDGs: What SDGs is your challenge related to? (please choose the top 3)\nsdgs: Zero hunger\nsdgs: Industry, innovation and infrastructure\nsdgs: Climate action\nsdgs: Life on land\nsdgs: Partnerships for the goals\nPartners\nPlease state the name of the Parter:\nUniversity of Cabo Verde, Public sector (Carry out studies and collect data on the feasibility',
        'Transitioning Agriculture Using the Internet of Things and Artificial Intelligence\nTitle\nPlease provide a name for your action learning plan.\nTransitioning Agriculture Using the Internet of Things and Artificial Intelligence\nChallenge statement\nChallenge type: If you are working on multiple challenges, please indicate if this is your "big bet" or "exploratory" challenge. \nPlease note: we ask you to only submit a maximum of 3 challenges - 1x Big Bet, 2x Exploratory. Each challenge must be submitted individually.\nEXPLORATORY\nChallenge statement: What is your challenge? (Please answer',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=1523',
    },
    {
      base: 'actionplan',
      doc_id: 1868,
      main_id: 'actionplan:1868',
      meta: {
        date: '2023-12-19T19:42:22.142334+00:00',
        doc_type: 'action plan',
        language: ['en'],
        status: 'public',
      },
      score: 0.4667409,
      snippets: [
        'y of Telecommunications which will be a crucial stakeholder in mobilizing funds and taking the following steps after implementing the DRA. Our country office will be supporting upcoming steps regarding AI.',
        'innovation (cross-country product)?\nTo what stage(s) in the learning cycle does your learning question relate?\nGrow\nInnovation methods: What are your top 5 key innovation methods or tools that you are planning to use for this learning question?\nmethods: Human Centered Design\nmethods: Collective Intelligence\nmethods: Co-creation\nUsage of methods: Relating to your choice above, how will you use your methods & tools for this learning question? What value do these add in answering your learning question?\nAction 1: Thinkia - citizen lab\nBy tapping on collective intelligence at the',
        'd collective intelligence to put together the DRA country study is fundamental, given the nature of the methodology. To get the knowledge of over 150+ experts from different sectors of society ads tremendous value to the sensemaking process that the literature analysis provides.\nClosing\nEarly leads to grow: Think about the possible grow phase for this challenge - who might benefit from your work on this challenge or who might be the champions in your country that you should inform or collaborate with early on to help you grow this challenge?\nAction 1: Thinkia - citizen lab\nTo',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=1868',
    },
    {
      base: 'actionplan',
      doc_id: 2127,
      main_id: 'actionplan:2127',
      meta: {
        date: '2024-03-08T13:05:08.194272+00:00',
        doc_type: 'action plan',
        iso3: [],
        language: ['en'],
        status: 'public',
      },
      score: 0.44140613,
      snippets: [
        'the system?\nWhile there are vast amounts on unstructured online data left by tourists to Malawi, the country has limited insights on various factors that promote or hinder tourism growth. Recent advancements in AI and machine learning have made it possible to generate almost real-time insights from such data sources.\nPartners\nPlease state the name of the partner:\nSDG AI Lab\nWhat sector does your partner belong to?\nUnited Nations\nPlease provide a brief description of the partnership.\nContracted to develop the AI model\nIs this a new and unusual partner for UNDP?\nNo\nPlease state the',
        "AI for Tourism: Improved data and insights for the development of an inclusive and viable tourism ...\nLearnings on your challenge\nWhat are the top key insights you generated about your learning challenge during this Action Learning Plan? (Please list a maximum of 5 key insights) \n1. The primary factor affecting tourism in Malawi was deemed to be \u2018underdeveloped infrastructure\u2019. This challenge's scope encompassed both service-related aspects and physical infrastructure.\n2. Three key drivers influencing under-developed infrastructure for tourism are: \ni) Lack of political will,\nii)",
        's of data, why did you chose these? What gaps in available data were these addressing?\nWe are developing an AI model that analyses publicly accessible online data, such as reviews on Booking.com and TripAdvisor, to understand and visualize insights on tourism in Malawi. There are no such dashboards currently.\nWhat key innovation methods did you ACTUALLY use?\nmethods: Artificial Intelligence/Machine Learning\nmethods: Data Visualisation\nmethods: Prototyping\nWhy was it necessary to apply the above innovation method on your frontier challenge? How did these help you to unpack the',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=2127',
    },
    {
      base: 'actionplan',
      doc_id: 2081,
      main_id: 'actionplan:2081',
      meta: {
        date: '2023-12-22T11:50:37.278341+00:00',
        doc_type: 'action plan',
        language: ['en'],
        status: 'public',
      },
      score: 0.4327761,
      snippets: ['d minotor the dumping sites via AI.'],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=2081',
    },
    {
      base: 'actionplan',
      doc_id: 2142,
      main_id: 'actionplan:2142',
      meta: {
        date: '2023-12-27T16:22:12.321127+00:00',
        doc_type: 'action plan',
        iso3: [],
        language: ['en'],
        status: 'public',
      },
      score: 0.40191004,
      snippets: [
        'process.\nUnforeseen internal challenges and delays are inevitable. Being flexible in our approach and adapting to unexpected obstacles is crucial for the success of the initiative.\nApplying diverse innovation methods, leveraging new data types, and engaging unusual partners generated unique insights unattainable by traditional means.\nReal-life machine learning dynamics emerged; potential for AI/ML to automate data flow and enhance advisory systems.\nConsidering the outcomes of this learning challenge, which of the following best describe the handover process? (Please select all that',
        'for UNDP?\nNo\nEnd\nBonus question: How did the interplay of innovation methods, new forms of data and unusual partners enable you to learn & generate insights, that otherwise you would have not been able to achieve?\nThe interplay of innovative methods, new data sources, and unconventional partnerships facilitated a holistic understanding of the agricultural landscape.\nCo-creation with farmers through participatory design and citizen science unveiled nuanced insights, while diverse data types enriched our perspective.\nCollaboration with ICAT and other partners brought domain',
        "r frontier challenge? How did these help you to unpack the system?\nCollective Intelligence allowed us to tap into the diverse perspectives of stakeholders, aggregating insights crucial for understanding the complex agrometeorological system.\nHuman-Centered Design ensured that our solution addressed real user needs, fostering better engagement and usability. This approach helped unpack the system by placing the end-users at the core of the solution development process.\nPartners\nPlease state the name of the partner:\nInstitut de Conseil et d'Appui Technique (ICAT)\nWhat sector does your",
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=2142',
    },
    {
      base: 'actionplan',
      doc_id: 1824,
      main_id: 'actionplan:1824',
      meta: {
        date: '2024-01-01T03:12:44.372590+00:00',
        doc_type: 'action plan',
        iso3: ['BGD', 'IDN', 'IND', 'MYS', 'PHL', 'USA'],
        language: ['en'],
        status: 'public',
      },
      score: 0.39752805,
      snippets: [
        "i youth, specifically 4th year CSE/IT university students, in emerging technologies such as AI/ML, AR/VR, Data Science, IoT, etc. by 2026. This is a a clear match on what the Lab has been developing and the model proposed by the lab addresses the government's concern of training a large number of youth in an effective manner which is also time and cost efficient.\nICT & Outsourcing, Comprehensive Private Sector Assessment, USAID, 2019. Private Sector Assessment: Exploring Markets and Investment Opportunities (revised recommendations due to COVID-19), USAID, 2020. Bangladesh datasets",
        'learning question? What value do these add in answering your learning question?\nCo-creation: Designing a rapid skilling methodology along with government. Pilot: Testing out a model for rapid up-skilling in technology space; Sensemaking: Carry out sector analysis on digital skills including domestic demand in Bangladesh and global market demand. Collective intelligence: Collaboration with multiple stakeholders, co-designing with different partners and decisions informed by muliptle-stakeholder consultations, surveys and discussions.\nNew sources of data: What types of new data',
        'o up-skill youth in emerging technologies in a cost and time efficient manner?\nCan this model be adapted to up-skill youth from less privileged backgrounds with access issues?\nTo what stage(s) in the learning cycle does your learning question relate?\nTest\nInnovation methods: What are your top 5 key innovation methods or tools that you are planning to use for this learning question?\nmethods: Sensemaking\nmethods: Pilots\nmethods: Collective Intelligence\nmethods: Co-creation\nUsage of methods: Relating to your choice above, how will you use your methods & tools for this learning',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=1824',
    },
    {
      base: 'actionplan',
      doc_id: 1777,
      main_id: 'actionplan:1777',
      meta: {
        date: '2023-12-05T04:26:51.667390+00:00',
        doc_type: 'action plan',
        iso3: ['AUT', 'SGP', 'USA', 'VNM'],
        language: ['en'],
        status: 'public',
      },
      score: 0.39054018,
      snippets: [
        'e from traditional top-down state management to serving people and putting citizen needs at the center of development. This mindset change is not unique to Viet Nam but has been influenced by global trends, such as budget cuts in the public sector, environmental degradation, rising demands from more educated and globally aware population.\nOver the past decades, Viet Nam has made remarkable achievements in economic development based on innovation and the application of advances in science and technology. The Global Innovation Index (GII) 2022 showed that Viet Nam ranked 48 out of',
        'o this challenge?\nOver the past few years, UNDP Viet Nam is seen by Viet Nam government counterpart as one of the key international organizations that is able to provide the technical expertise and support suited to its development needs. In this challenge, Accelerator Lab Viet Nam is the connecting bridge between government partners to build innovation capacity for leading government agencies that are working on innovation in Viet Nam and connect key innovation drivers towards a common goal which is to improve innovation ecosystem in Viet Nam.\nAs a public sector organziation UNDP',
        'of 132 countries and territories and belonged to the group of countries that have made the greatest progress over the past decade. Studies at Viet Nam Venture Summit 2022 showed that Viet Nam was in the golden triangle of Southeast Asia for investment in innovation in general and startups in particular.\nAccording to UNDP and NIC report, process innovation is the most common type of innovation in the public sector of Vietnam (54.5% of respondents in MPI and 60% of respondents in 3 provinces implementing process innovation), followed by product and service innovation. However, the',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=1777',
    },
    {
      base: 'actionplan',
      doc_id: 2044,
      main_id: 'actionplan:2044',
      meta: {
        date: '2024-01-09T03:13:45.424945+00:00',
        doc_type: 'action plan',
        iso3: ['GBR', 'IDN'],
        language: ['en'],
        status: 'public',
      },
      score: 0.3900625,
      snippets: [
        '. Overall, from the innovative methods we use we were able to learn and generate insights that are relevant and have served as a stepping stone for a establishing cooperation between the UN system (including UNDP) and a new government partner, the Nusantara Capital City Authority. In particular, this use of generative AI for urban planning is arguably the first of its kind in Indonesia.',
        "a were these addressing?\nIn terms of data, Nusantara can be said to be a sandbox as existing data is used to speculate about what the future capital city will look like. The use of a public survey as well as rapid ethnography, workshops, and interviews provided insights on the aspirations of existing local residents as well as the nation's citizens alike, and paired with existing government policy,\nWhat key innovation methods did you ACTUALLY use?\nmethods: Anticipatory Regulation\nmethods: Artificial Intelligence/Machine Learning\nmethods: Co-creation\nmethods: Collective",
        'Collective Intelligence\nmethods: Data Visualisation\nmethods: Ethnography\nmethods: Foresight\nmethods: Participatory Design\nWhy was it necessary to apply the above innovation method on your frontier challenge? How did these help you to unpack the system?\nThe use of anticipatory methods including foresight was indeed necessary because we are dealing with an urban area that does not yet exist. Thus, parts of the work are speculative and serve to build robust policies to address issues that may arise based on the identified trends on the ground. The use of participatory methods aims to',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=2044',
    },
    {
      base: 'actionplan',
      doc_id: 1816,
      main_id: 'actionplan:1816',
      meta: {
        date: '2023-05-19T10:59:09.715164+00:00',
        doc_type: 'action plan',
        iso3: ['CPV', 'DEU', 'NUL', 'USA'],
        language: ['en'],
        status: 'public',
      },
      score: 0.38771307,
      snippets: [
        'question? What value do these add in answering your learning question?\nTo conduct a wide collective intelligence process using system thinking approach to involve a large number of stakeholders from the private sector, the financial ecosystem and other institutions to help crowdsource information and reports from companies and business into a platform that can help assess business performance and contribution to sustainable development.\nNew sources of data: What types of new data sources are you using for this learning question?\ndatasources: interviews\ndatasources: quantitative and',
        'n companies can help induce increased investment in sustainable development that promotes economic growth and progress towards SDGs.\nTo what stage(s) in the learning cycle does your learning question relate?\nSense\nExplore\nTest\nInnovation methods: What are your top 5 key innovation methods or tools that you are planning to use for this learning question?\nmethods: System Thinking\nmethods: Minimal Viable Product (MVP)\nmethods: Crowdsourcing\nmethods: Collective Intelligence\nUsage of methods: Relating to your choice above, how will you use your methods & tools for this learning question?',
        's objective can be achieved in 3 to 5 years. Over time, depending on the evolution of the participating companies, categories may be created, which will also highlight sectors of activity. In the future, companies from the State Business Sector may also be covered. A database with sectorial information can be built, for example, by creating a Sectorial Average Balance Sheet. From here, benchmarks, diagnostics and SWOT analysis can be created.',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=1816',
    },
    {
      base: 'actionplan',
      doc_id: 1789,
      main_id: 'actionplan:1789',
      meta: {
        date: '2023-05-19T10:33:32.061288+00:00',
        doc_type: 'action plan',
        iso3: ['DEU', 'FRA'],
        language: ['en'],
        status: 'public',
      },
      score: 0.38298053,
      snippets: [
        'finetuning solution prototypes. Systems thinking will be used to analyze the complexity of the challenge and identify potential leverage points for intervention. Of course, collective intelligence methods are at the heart of the exercise itself to ensure community participation and involvement.\nNew sources of data: What types of new data sources are you using for this learning question?\ndatasources: Sensor & sensor network data\ndatasources: Citizen data\ndatasources: crowdsourced photos\nExisting data gaps: Relating to your choice above, what existing gaps in data or information do',
        ') in the learning cycle does your learning question relate?\nExplore\nTest\nInnovation methods: What are your top 5 key innovation methods or tools that you are planning to use for this learning question?\nmethods: Design Thinking\nmethods: Collective Intelligence\nmethods: Co-creation\nUsage of methods: Relating to your choice above, how will you use your methods & tools for this learning question? What value do these add in answering your learning question?\nHuman-centered co-creation workshops will be used to involve stakeholders in the process of designing, testing, and finetuning',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=1789',
    },
    {
      base: 'actionplan',
      doc_id: 1999,
      main_id: 'actionplan:1999',
      meta: {
        date: '2023-12-22T09:30:13.283609+00:00',
        doc_type: 'action plan',
        iso3: ['JPN', 'VNM'],
        language: ['en'],
        status: 'public',
      },
      score: 0.37642568,
      snippets: [
        'n a fast-paced environment where timely solutions are needed.\nLeveraging Diverse Insights: Collective intelligence ensured that the solutions were not developed in a vacuum but were informed by a broad spectrum of knowledge and experience.\nPartners\nPlease state the name of the partner:\nNational Agency for Technology Entrepreneurship and Commercialization Development, Ministry Of Science and Technology \u2013 Government \nNational Innovation Center, Ministry of Planning and Investment \u2013 Government \nCenter for Entrepreneurship and Innovation, Fullbright University Vietnam \u2013 Academia',
        "Closing of: Public Sector Innovation Changemakers Journey & Playbook for civil servants\nLearnings on your challenge\nWhat are the top key insights you generated about your learning challenge during this Action Learning Plan? (Please list a maximum of 5 key insights) \nPublic sector innovation in Vietnam's socialist republic governance structure has evolved significantly over the years. The government has moved from traditional command-control state management to a more inclusive and participatory approach, putting citizen needs at the center of development. This shift requires a new",
        'g higher level designation to be gatekeeper of certain field rather than act and someone else might get credit for it. This limits the development of innovation ecosystem in Viet Nam. In this changemaker transformation and public sector innovation playbook development journey, AccLab VN succeeded in bringing 2 key public drivers in the ecosystem (NATEC and NIC) and their subsidiaries to work together to learn about innovation concept, innovation tools and design the playbook together for public servants like themselves.\nNumerous innovation tools which have been used not only in',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=1999',
    },
    {
      base: 'actionplan',
      doc_id: 2140,
      main_id: 'actionplan:2140',
      meta: {
        date: '2024-02-04T21:39:52.765057+00:00',
        doc_type: 'action plan',
        iso3: ['USA'],
        language: ['en'],
        status: 'public',
      },
      score: 0.3667358,
      snippets: [
        'e managed b the team.\nPlease paste any link(s) to blog(s) or publication(s) that articulate the learnings on your frontier challenge.\nhttps://app.mural.co/t/montacerboard3353/m/montacerboard3353/1703141965671/57951b09bf85d9072a6dba3ce99b56b6b88d1891?sender=u8de91889c5af901d25463935\nData and Methods\nWhat (new) types of data did you ACTUALLY use?\ndatasources: academic literature\ndatasources: Citizen data\ndatasources: citizen-generated data\ndatasources: crowd source\ndatasources: future analysis: identify emerging ai-driven job roles and required skills. scenario planning: develop',
        's photo stories, research calls, and community engagement to actively generate real-time and updated data.\nStakeholder Mapping: Identifying key stakeholders to actively engage and garner support for data generation, as well as enhancing our comprehension of the challenges at hand.\nSystem Mapping: Aiming to comprehend the multifaceted challenges as a system, with multiple actors and components interacting in complex ways.\nWhat key innovation methods did you ACTUALLY use?\nmethods: Co-creation\nmethods: Data Ethography\nmethods: Human Centered Design\nmethods: Solutions Mapping\nmethods:',
      ],
      url: 'https://learningplans.sdg-innovation-commons.org/en/view/pad?id=2140',
    },
  ],
  status: 'ok',
};
