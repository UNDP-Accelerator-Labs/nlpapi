import { ApiProvider, DEFAULT_API } from '../api/api';
import { ALL_FIELDS, PAGE_SIZE } from '../misc/constants';
import { SearchFilters, SearchResult, Stats } from './types';

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
