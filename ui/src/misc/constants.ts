import { DBName, DeepDiveName, VersionResponse } from '../api/types';

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
export const PAGE_SIZE = 10;
export const DISPLAY_PAGE_COUNT = 10;
export const MID_PAGE = Math.floor(DISPLAY_PAGE_COUNT / 2);
export const ALL_FIELDS = ['doc_type', 'iso3', 'language', 'status'];

const HOST_URL = `${window.location.origin}`;
const LIVE_URL = 'https://nlpapi.sdg-innovation-commons.org';

const VERSION_OBJS: { [key: string]: VersionResponse } = {};

const getVersionObj = async (base = '') => {
  try {
    if (!VERSION_OBJS[base]) {
      const versionResponse = await fetch(`${base}/api/version`);
      const versionObj: VersionResponse = await versionResponse.json();
      VERSION_OBJS[base] = versionObj;
    }
    return VERSION_OBJS[base];
  } catch (_) {
    const res: VersionResponse = {
      app_name: 'error',
      app_commit: 'error',
      python: 'error',
      deploy_date: 'error',
      start_date: 'error',
      has_vecdb: false,
      has_llm: false,
      vecdbs: [],
      deepdives: [],
      error: ['error'],
    };
    return res;
  }
};

let SEARCH_API: string | null = null;

export const getSearchApiUrl = async () => {
  if (!SEARCH_API) {
    const versionObj = await getVersionObj();
    if (versionObj.error || !versionObj.has_vecdb) {
      SEARCH_API = LIVE_URL;
    } else {
      SEARCH_API = HOST_URL;
    }
    // console.log(`search api: ${SEARCH_API}`);
  }
  return SEARCH_API;
};

let COLLECTION_API: string | null = null;

export const getCollectionApiUrl = async () => {
  if (!COLLECTION_API) {
    const versionObj = await getVersionObj();
    if (versionObj.error) {
      COLLECTION_API = LIVE_URL;
    } else {
      COLLECTION_API = HOST_URL;
    }
    // console.log(`collection api: ${COLLECTION_API}`);
  }
  return COLLECTION_API;
};

export const LOGIN_URL = 'https://login.sdg-innovation-commons.org/login';

let DEEP_DIVES: DeepDiveName[] | null = null;

export const getDeepDives = async () => {
  if (!DEEP_DIVES) {
    const versionObj = await getVersionObj();
    DEEP_DIVES = versionObj.deepdives;
  }
  return DEEP_DIVES;
};

let VEC_DBS: DBName[] | null = null;

export const getVecDBs = async () => {
  if (!VEC_DBS) {
    const versionObj = await getVersionObj();
    if (versionObj.error || !versionObj.has_vecdb) {
      const liveVersion = await getVersionObj(LIVE_URL);
      VEC_DBS = liveVersion.vecdbs;
    } else {
      VEC_DBS = versionObj.vecdbs;
    }
  }
  return VEC_DBS;
};
