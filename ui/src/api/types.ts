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
export type ApiUserResult = {
  name: string | undefined;
};

export type UserResult = {
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
  q: string;
  filter: string;
  p: number;
};
