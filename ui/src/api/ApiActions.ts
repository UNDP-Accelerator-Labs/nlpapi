/**
 * NLP-API provides useful Natural Language Processing capabilities as API.
 * Copyright (C) 2024 UNDP Accelerator Labs, Josua Krause
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
import { ApiProvider, DEFAULT_API } from '../api/api';
import { ALL_FIELDS, PAGE_SIZE } from '../misc/constants';
import { SearchFilters, SearchResult, Stats } from './types';

type UserCallback = (userName: string | undefined) => void;
type StatCallback = (stats: Stats) => void;
type ResultCallback = (results: SearchResult) => void;

export default class ApiActions {
  private readonly api: ApiProvider;

  private statNum: number;
  private responseNum: number;

  constructor(api?: ApiProvider) {
    this.api = api ?? DEFAULT_API;
    this.statNum = 0;
    this.responseNum = 0;
  }

  async user(cb: UserCallback) {
    const { userName } = await this.api.user();
    cb(userName);
  }

  async search(
    query: string,
    filters: SearchFilters,
    page: number,
    cb: ResultCallback,
  ) {
    this.responseNum += 1;
    const responseNum = this.responseNum;
    const result = await this.api.search(
      query,
      filters,
      page * PAGE_SIZE,
      PAGE_SIZE,
    );
    if (responseNum !== this.responseNum) {
      return;
    }
    const { hits, status } = result;
    cb({
      hits: hits.map(
        ({ base, doc_id, main_id, meta, score, snippets, url, title }) => {
          const { date, doc_type, iso3, language, status } = meta;
          return {
            base,
            docId: doc_id,
            mainId: main_id,
            meta: {
              date,
              docType: doc_type,
              iso3,
              language,
              status,
            },
            score,
            snippets,
            url,
            title,
          };
        },
      ),
      status,
    });
  }

  async stats(filters: SearchFilters, cb: StatCallback) {
    this.statNum += 1;
    const statNum = this.statNum;
    const { doc_count, fields } = await this.api.stats(ALL_FIELDS, filters);
    if (statNum !== this.statNum) {
      return;
    }
    cb({ count: doc_count, fields });
  }
} // ApiActions
