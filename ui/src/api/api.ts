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
  ApiCollectionResponse,
  ApiDocumentListResponse,
  ApiDocumentResponse,
  ApiSearchResult,
  ApiStatResult,
  ApiUserResult,
  CollectionListResponse,
  CollectionResponse,
  DeepDive,
  DocumentListResponse,
  DocumentResponse,
  FulltextResponse,
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
  addCollection: (
    name: string,
    deepDive: DeepDive,
  ) => Promise<CollectionResponse>;
  collections: () => Promise<CollectionListResponse>;
  addDocuments: (
    collectionId: number,
    mainIds: string[],
  ) => Promise<DocumentResponse>;
  documents: (collectionId: number) => Promise<DocumentListResponse>;
  getFulltext: (mainId: string) => Promise<FulltextResponse>;
  requeue: (collectionId: number, mainIds: string[]) => Promise<void>;
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
  addCollection: async (name, deepDive) => {
    const url = await getCollectionApiUrl();
    const res = await fetch(`${url}/api/collection/add`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        deep_dive: deepDive,
      }),
    });
    const { collection_id }: ApiCollectionResponse = await res.json();
    return {
      collectionId: collection_id,
    };
  },
  collections: async () => {
    const url = await getCollectionApiUrl();
    const res = await fetch(`${url}/api/collection/list`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    const { collections }: CollectionListResponse = await res.json();
    return { collections };
  },
  addDocuments: async (collectionId, mainIds) => {
    const url = await getCollectionApiUrl();
    const res = await fetch(`${url}/api/documents/add`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        collection_id: collectionId,
        main_ids: mainIds,
      }),
    });
    const { document_ids }: ApiDocumentResponse = await res.json();
    return { documentIds: document_ids };
  },
  documents: async (collectionId) => {
    const url = await getCollectionApiUrl();
    const res = await fetch(`${url}/api/documents/list`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        collection_id: collectionId,
      }),
    });
    const { documents }: ApiDocumentListResponse = await res.json();
    return {
      documents: documents.map(
        ({
          id,
          main_id,
          url,
          title,
          deep_dive,
          verify_key,
          deep_dive_key,
          is_valid,
          verify_reason,
          deep_dive_result,
          error,
        }) => ({
          id,
          mainId: main_id,
          url,
          title,
          collectionId: deep_dive,
          verifyKey: verify_key,
          deepDiveKey: deep_dive_key,
          isValid: is_valid ?? undefined,
          verifyReason: verify_reason ?? undefined,
          deepDiveResult: deep_dive_result ?? undefined,
          error: error ?? undefined,
        }),
      ),
    };
  },
  getFulltext: async (mainId) => {
    const url = await getCollectionApiUrl();
    const res = await fetch(`${url}/api//documents/fulltext`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        main_id: mainId,
      }),
    });
    const { content, error }: FulltextResponse = await res.json();
    return { content: content ?? undefined, error: error ?? undefined };
  },
  requeue: async (collectionId, mainIds) => {
    const url = await getCollectionApiUrl();
    const res = await fetch(`${url}/api/documents/requeue`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        collection_id: collectionId,
        main_ids: mainIds,
      }),
    });
    await res.json();
  },
};
