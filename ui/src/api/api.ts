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
import { getCollectionApiUrl, getSearchApiUrl } from '../misc/constants';
import {
  ApiSearchResult,
  ApiStatResult,
  ApiUserResult,
  SearchFilters,
  UserResult,
} from './types';

export type ApiProvider = {
  user: () => Promise<UserResult>;
  stats: (
    fields: Readonly<string[]>,
    filters: Readonly<SearchFilters>,
  ) => Promise<ApiStatResult>;
  search: (
    input: Readonly<string>,
    filters: Readonly<SearchFilters>,
    offset: number,
    limit: number,
  ) => Promise<ApiSearchResult>;
};

export const DEFAULT_API: ApiProvider = {
  user: async () => {
    const url = await getCollectionApiUrl();
    try {
      const res = await fetch(`${url}/api/user`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });
      const { name }: ApiUserResult = await res.json();
      return {
        userName: name ?? undefined,
      };
    } catch (err) {
      console.error(err);
      return {
        userName: undefined,
      };
    }
  },
  stats: async (fields, filters) => {
    const url = await getSearchApiUrl();
    try {
      const res = await fetch(`${url}/api/stats`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ fields, filters }),
      });
      return await res.json();
    } catch (err) {
      console.error(err);
      return {
        doc_count: -1,
        fields: {},
      };
    }
  },
  search: async (input, filters, offset, limit) => {
    const url = await getSearchApiUrl();
    try {
      const res = await fetch(`${url}/api/search`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input,
          filters,
          offset,
          limit,
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
  },
};
