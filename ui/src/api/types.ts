export type ApiUserResult = {
  name: string | undefined;
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
