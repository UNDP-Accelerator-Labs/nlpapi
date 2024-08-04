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
export type DBName = 'main' | 'test' | 'rave_ce';
export type DeepDiveName = 'circular_economy' | 'circular_economy_undp';

export type VersionResponse = {
  app_name: string;
  app_commit: string;
  python: string;
  deploy_date: string;
  start_date: string;
  has_vecdb: boolean;
  has_llm: boolean;
  vecdbs: DBName[];
  deepdives: DeepDiveName[];
  error: string[] | undefined;
};

export type ApiUserResult = {
  uuid: string | undefined;
  name: string | undefined;
};

export type UserResult = {
  userId: string | undefined;
  userName: string | undefined;
};

export type SearchFilters = { [key: string]: string[] };

export type ApiStatResult = {
  doc_count: number;
  fields: { [key: string]: { [key: string]: number } };
};

export type Stats = {
  count?: number;
  fields: { [key: string]: { [key: string]: number | undefined } };
};

export type ApiSearchResult = {
  hits: {
    base: string;
    doc_id: number;
    main_id: string;
    meta: {
      date: string;
      doc_type: string;
      iso3?: string[];
      language?: string[];
      status: string;
    };
    score: number;
    snippets: string[];
    url: string;
    title: string;
  }[];
  status: string;
};

export type SearchResult = {
  hits: {
    base: string;
    docId: number;
    mainId: string;
    meta: {
      date: string;
      docType: string;
      iso3?: string[];
      language?: string[];
      status: string;
    };
    score: number;
    snippets: string[];
    url: string;
    title: string;
  }[];
  status: string;
};

export type SearchState = {
  db: DBName;
  q: string;
  filter: string;
  p: number;
};

export type InfoResult = {
  url: string | undefined;
  title: string | undefined;
  error: string | undefined;
};

export type Collection = {
  id: number;
  user: string;
  name: string;
  deepDiveKey: string;
  isPublic: boolean;
};

type ApiCollection = {
  id: number;
  user: string;
  name: string;
  deep_dive_key: string;
  is_public: boolean;
};

export type CollectionOptions = {
  isPublic: boolean;
};

type DeepDiveResult = {
  reason: string;
  cultural: number;
  economic: number;
  educational: number;
  institutional: number;
  legal: number;
  political: number;
  technological: number;
};

type ApiDocumentObj = {
  id: number;
  main_id: string;
  url: string;
  title: string;
  deep_dive: number;
  verify_key: string;
  deep_dive_key: string;
  is_valid: boolean | undefined;
  verify_reason: string | undefined;
  deep_dive_result: DeepDiveResult | undefined;
  error: string | undefined;
  tag: string | undefined;
  tag_reason: string | undefined;
};

export type StatNumbers = { [key: string]: number | undefined };
export type StatFull = {
  [key: string]: { mean: number; stddev: number; count: number } | undefined;
};
export type StatFinal = {
  [key: string]: { mean: number; ciMax: number; ciMin: number } | undefined;
};

export type DocumentObj = {
  id: number;
  mainId: string;
  url: string;
  title: string;
  collectionId: number;
  verifyKey: string;
  deepDiveKey: string;
  isValid: boolean | undefined;
  verifyReason: string | undefined;
  scores: StatNumbers;
  scoresFull: StatFull;
  deepDiveReason: string | undefined;
  error: string | undefined;
  tag: string | undefined;
  tagReason: string | undefined;
};

export type ApiCollectionResponse = {
  collection_id: number;
};

export type CollectionResponse = {
  collectionId: number;
};

export type ApiCollectionListResponse = {
  collections: ApiCollection[];
};

export type CollectionListResponse = {
  collections: Collection[];
};

export type ApiDocumentResponse = {
  document_ids: number[];
};

export type DocumentResponse = {
  documentIds: number[];
};

export type ApiDocumentListResponse = {
  documents: ApiDocumentObj[];
  is_readonly: boolean;
};

export type DocumentListResponse = {
  documents: DocumentObj[];
  isReadonly: boolean;
};

export type FulltextResponse = {
  content: string | undefined;
  error: string | undefined;
};

export type Filter =
  | 'total'
  | 'pending'
  | 'included'
  | 'excluded'
  | 'complete'
  | 'errors';

export type DocumentStats = {
  [key in Filter]: number;
};

export const STAT_NAMES = {
  total: 'Total',
  pending: 'Pending',
  included: 'Included',
  excluded: 'Excluded',
  complete: 'Complete',
  errors: 'Errors',
};
