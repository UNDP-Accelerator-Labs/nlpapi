export const PAGE_SIZE = 10;
export const DISPLAY_PAGE_COUNT = 10;
export const MID_PAGE = Math.floor(DISPLAY_PAGE_COUNT / 2);
export const ALL_FIELDS = ['doc_type', 'iso3', 'language', 'status'];

type VersionResponse = {
  app_name: string;
  app_commit: string;
  python: string;
  deploy_date: string;
  start_date: string;
  has_vecdb: boolean;
  has_llm: boolean;
  error: string[] | undefined;
};

const HOST_URL = `${window.location.origin}`;
const LIVE_URL = 'https://nlpapi.sdg-innovation-commons.org';

const getVersionObj = async () => {
  try {
    const url = window.location.origin.includes('localhost')
      ? 'http://localhost:8080/api/version'
      : '/api/version';
    const versionResponse = await fetch(url);
    const versionObj: VersionResponse = await versionResponse.json();
    return versionObj;
  } catch (_) {
    const res: VersionResponse = {
      app_name: 'error',
      app_commit: 'error',
      python: 'error',
      deploy_date: 'error',
      start_date: 'error',
      has_vecdb: false,
      has_llm: false,
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
  }
  return SEARCH_API;
};
