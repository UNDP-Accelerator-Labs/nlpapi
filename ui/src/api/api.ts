import { getSearchApiUrl } from '../misc/constants';
import { ApiSearchResult, ApiStatResult, SearchFilters } from './types';

export type ApiProvider = {
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
