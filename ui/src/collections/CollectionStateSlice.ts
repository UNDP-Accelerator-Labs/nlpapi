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
  collectionName: string | undefined;
  collectionUser: string | undefined;
  collectionIsPublic: boolean;
  collectionFilter: Filter;
  collectionTag: string | null;
  cmpCollectionId: number;
  cmpCollectionTag: string | null;
};

type SetCollectionAction = {
  payload: {
    isCmp: boolean;
    collectionId: number;
  };
};

type SetCollectionInfoAction = {
  payload: {
    collectionName: string | undefined;
    collectionUser: string | undefined;
    collectionIsPublic: boolean;
  };
};

type SetCollectionFilterAction = {
  payload: {
    collectionFilter: Filter;
  };
};

type SetCollectionTagAction = {
  payload: {
    isCmp: boolean;
    collectionTag: string | null;
  };
};

type CollectionReducers = {
  setCollection: (state: CollectionState, action: SetCollectionAction) => void;
  setCollectionInfo: (
    state: CollectionState,
    action: SetCollectionInfoAction,
  ) => void;
  setCollectionFilter: (
    state: CollectionState,
    action: SetCollectionFilterAction,
  ) => void;
  setCollectionTag: (
    state: CollectionState,
    action: SetCollectionTagAction,
  ) => void;
};

const getName = (name: string, isCmp: boolean): string => {
  return `${name}${isCmp ? 'Cmp' : ''}`;
};

const collectionStateSlice = createSlice<
  CollectionState,
  CollectionReducers,
  string
>({
  name: 'collectionState',
  initialState: {
    collectionId: +(
      localStorage.getItem(getName('collection', false)) ?? '-1'
    ),
    collectionName: undefined,
    collectionUser: undefined,
    collectionIsPublic: false,
    collectionFilter: (localStorage.getItem(
      getName('collectionFilter', false),
    ) ?? 'complete') as Filter,
    collectionTag:
      localStorage.getItem(getName('collectionTag', false)) ?? null,
    cmpCollectionId: +(
      localStorage.getItem(getName('collection', true)) ?? '-1'
    ),
    cmpCollectionTag:
      localStorage.getItem(getName('collectionTag', true)) ?? null,
  },
  reducers: {
    setCollection: (state, action) => {
      const { collectionId, isCmp } = action.payload;
      if (isCmp) {
        state.cmpCollectionId = collectionId;
        state.cmpCollectionTag = null;
      } else {
        state.collectionId = collectionId;
        state.collectionFilter = 'complete';
        state.collectionTag = null;
        localStorage.removeItem('collectionFilter');
      }
      localStorage.setItem(getName('collection', isCmp), `${collectionId}`);
      localStorage.removeItem(getName('collectionTag', isCmp));
    },
    setCollectionInfo: (state, action) => {
      const { collectionName, collectionUser, collectionIsPublic } =
        action.payload;
      state.collectionName = collectionName;
      state.collectionUser = collectionUser;
      state.collectionIsPublic = collectionIsPublic;
    },
    setCollectionFilter: (state, action) => {
      const { collectionFilter } = action.payload;
      state.collectionFilter = collectionFilter;
      localStorage.setItem('collectionFilter', collectionFilter);
    },
    setCollectionTag: (state, action) => {
      const { collectionTag, isCmp } = action.payload;
      if (isCmp) {
        state.cmpCollectionTag = collectionTag;
      } else {
        state.collectionTag = collectionTag;
      }
      if (collectionTag) {
        localStorage.setItem(getName('collectionTag', isCmp), collectionTag);
      } else {
        localStorage.removeItem(getName('collectionTag', isCmp));
      }
    },
  },
});

export const {
  setCollection,
  setCollectionInfo,
  setCollectionFilter,
  setCollectionTag,
} = collectionStateSlice.actions;

export default collectionStateSlice.reducer;
