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
import { createSlice } from '@reduxjs/toolkit';
import { DBName, SearchFilters } from '../api/types';

type SearchState = {
  db: Readonly<DBName>;
  query: Readonly<string>;
  filters: Readonly<SearchFilters>;
  page: number;
};

type SetAction = {
  payload: {
    db: Readonly<DBName>;
    query: Readonly<string>;
    filters: Readonly<SearchFilters>;
    page: number;
  };
};

type SearchReducers = {
  setSearch: (state: SearchState, action: SetAction) => void;
};

const searchStateSlice = createSlice<SearchState, SearchReducers, string>({
  name: 'searchState',
  initialState: () => {
    const params = new URL(window.location.href).searchParams;
    let newDB = (localStorage.getItem('vecdb') ?? 'main') as DBName;
    let newQuery = '';
    let newFilters = {};
    let newPage = 0;
    const urlDB = params.get('db');
    if (urlDB) {
      newDB = urlDB as DBName;
    }
    const query = params.get('q');
    if (query) {
      newQuery = query;
    }
    const filters = params.get('filters');
    try {
      if (filters) {
        const filtersObj = JSON.parse(filters);
        newFilters = filtersObj;
      }
    } catch (_) {
      // nop
    }
    const page = params.get('p');
    if (page !== undefined && page !== null) {
      const pageNum = +page;
      if (Number.isFinite(pageNum)) {
        newPage = pageNum;
      }
    }
    return {
      db: newDB,
      query: newQuery,
      filters: newFilters,
      page: newPage,
    };
  },
  reducers: {
    setSearch: (state, action) => {
      const { db, query, filters, page } = action.payload;
      if (state.db !== db) {
        localStorage.setItem('vecdb', `${db}`);
        state.db = db;
      }
      state.query = query;
      state.filters = filters;
      state.page = page;
    },
  },
});

export const { setSearch } = searchStateSlice.actions;

export default searchStateSlice.reducer;
