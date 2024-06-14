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
