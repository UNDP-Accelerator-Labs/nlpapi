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
import { SearchFilters } from '../api/types';

type SearchState = {
  query: Readonly<string>;
  filters: Readonly<SearchFilters>;
  page: number;
};

type SetAction = {
  payload: {
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
  initialState: {
    query: '',
    filters: {},
    page: 0,
  },
  reducers: {
    setSearch: (state, action) => {
      const { query, filters, page } = action.payload;
      state.query = query;
      state.filters = filters;
      state.page = page;
    },
  },
});

export const { setSearch } = searchStateSlice.actions;

export default searchStateSlice.reducer;
