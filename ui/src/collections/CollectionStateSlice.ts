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
import { Filter } from '../api/types';

type CollectionState = {
  collectionId: number;
  collectionFilter: Filter;
};

type SetCollectionAction = {
  payload: {
    collectionId: number;
  };
};

type SetCollectionFilterAction = {
  payload: {
    collectionFilter: Filter;
  };
};

type CollectionReducers = {
  setCurrentCollection: (
    state: CollectionState,
    action: SetCollectionAction,
  ) => void;
  setCurrentCollectionFilter: (
    state: CollectionState,
    action: SetCollectionFilterAction,
  ) => void;
};

const collectionStateSlice = createSlice<
  CollectionState,
  CollectionReducers,
  string
>({
  name: 'collectionState',
  initialState: {
    collectionId: +(localStorage.getItem('collection') ?? '-1'),
    collectionFilter: (localStorage.getItem('collectionFilter') ??
      'complete') as Filter,
  },
  reducers: {
    setCurrentCollection: (state, action) => {
      const { collectionId } = action.payload;
      state.collectionId = collectionId;
      state.collectionFilter = 'complete';
      localStorage.setItem('collection', `${collectionId}`);
      localStorage.removeItem('collectionFilter');
    },
    setCurrentCollectionFilter: (state, action) => {
      const { collectionFilter } = action.payload;
      state.collectionFilter = collectionFilter;
      localStorage.setItem('collectionFilter', collectionFilter);
    },
  },
});

export const { setCurrentCollection, setCurrentCollectionFilter } =
  collectionStateSlice.actions;

export default collectionStateSlice.reducer;
