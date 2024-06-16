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
import {
  Collection,
  DeepDive,
  DocumentObj,
  SearchFilters,
  SearchResult,
  Stats,
} from './types';

type UserCallback = (userName: string | undefined) => void;
type StatCallback = (stats: Stats) => void;
type ResultCallback = (results: SearchResult) => void;
type AddCallback = () => void;
type AddCollectionCallback = (collectionId: number) => void;
type AddDocumentsCallback = (newDocs: number) => void;
type CollectionCallback = (collections: Collection[]) => void;
type DocumentCallback = (documents: DocumentObj[]) => void;
type FulltextCallback = (
  mainId: string,
  content: string | undefined,
  error: string | undefined,
) => void;

export default class ApiActions {
  private readonly api: ApiProvider;

  private statNum: number;
  private responseNum: number;
  private collectionsNum: number;
  private documentsNum: number;

  constructor(api?: ApiProvider) {
    this.api = api ?? DEFAULT_API;
    this.statNum = 0;
    this.responseNum = 0;
    this.collectionsNum = 0;
    this.documentsNum = 0;
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

  async addCollection(
    name: string,
    deepDive: DeepDive,
    cb: AddCollectionCallback,
  ) {
    const { collectionId } = await this.api.addCollection(name, deepDive);
    cb(collectionId);
  }

  async collections(cb: CollectionCallback) {
    this.collectionsNum += 1;
    const collectionsNum = this.collectionsNum;
    const { collections } = await this.api.collections();
    if (collectionsNum !== this.collectionsNum) {
      return;
    }
    cb(collections);
  }

  async addDocuments(
    collectionId: number,
    mainIds: string[],
    cb: AddDocumentsCallback,
  ) {
    const { documentIds } = await this.api.addDocuments(collectionId, mainIds);
    cb(documentIds.length);
  }

  async documents(collectionId: number, cb: DocumentCallback) {
    this.documentsNum += 1;
    const documentsNum = this.documentsNum;
    const { documents } = await this.api.documents(collectionId);
    if (documentsNum !== this.documentsNum) {
      return;
    }
    cb(documents);
  }

  async getFulltext(mainId: string, cb: FulltextCallback) {
    const { content, error } = await this.api.getFulltext(mainId);
    cb(mainId, content, error);
  }

  async requeue(collectionId: number, mainIds: string[], cb: AddCallback) {
    await this.api.requeue(collectionId, mainIds);
    cb();
  }
} // ApiActions
