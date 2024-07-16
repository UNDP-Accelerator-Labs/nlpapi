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
import React, {
  ChangeEventHandler,
  KeyboardEventHandler,
  MouseEventHandler,
  PureComponent,
  ReactNode,
} from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled, { css } from 'styled-components';
import ApiActions from '../api/ApiActions';
import { DBName, SearchFilters, SearchResult, Stats } from '../api/types';
import Collections from '../collections/Collections';
import { DISPLAY_PAGE_COUNT, MID_PAGE, PAGE_SIZE } from '../misc/constants';
import { RootState } from '../store';
import { setSearch } from './SearchStateSlice';

const VMain = styled.div`
  display: flex;
  justify-content: start;
  flex-direction: column;
  flex-grow: 1;
  height: 100vh;
  max-height: 100vh;
  max-width: 60vw;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
    max-width: 100vw;
    height: auto;
  }
`;

const VSide = styled.div`
  display: flex;
  justify-content: start;
  flex-direction: column;
  flex-grow: 1;
  height: 100vh;
  max-height: 100vh;
  max-width: 15vw;
  margin-right: 5px;

  @media (hover: none) and (max-width: 480px) {
    max-width: 100vw;
    height: auto;
  }
`;

const TopLeft = styled.div`
  min-height: 20vh;
  flex-shrink: 0;
  flex-grow: 0;
  margin: 2px;

  display: flex;
  flex-direction: column;
  justify-content: end;

  @media (hover: none) and (max-width: 480px) {
    width: 100vw;
    height: auto;
    min-height: 0;
  }
`;

const FilterDiv = styled.div`
  margin: 2px;
  overflow: auto;

  @media (hover: none) and (max-width: 480px) {
    width: 100vw;
  }
`;

type FieldProps = {
  'data-group': string;
};

const Field = styled.div<FieldProps>``;

type FieldNameProps = {
  isGroupSelected: boolean;
};

const FieldName = styled.div<FieldNameProps>`
  cursor: pointer;
  background-color: ${({ isGroupSelected }) =>
    isGroupSelected ? 'lightgray' : 'silver'};
  margin: 0;
  padding: 5px;

  &:hover {
    background-color: gray;
  }
`;

const FieldUl = styled.ul<FieldNameProps>`
  list-style-type: none;
  list-style-position: inside;
  margin: 0;
  padding: 5px;
`;

type FieldLiProps = {
  'isFieldSelected': boolean;
  'data-group': string;
  'data-field': string;
};

const FieldLi = styled.li<FieldLiProps>`
  list-style-type: none;
  list-style-position: inside;
  margin: 0;
  padding: 5px;
  padding-left: 10px;
  cursor: pointer;

  background-color: ${({ isFieldSelected }) =>
    isFieldSelected ? 'lightsalmon' : 'inherit'};

  &:hover {
    background-color: ${({ isFieldSelected }) =>
      isFieldSelected ? 'salmon' : 'lightgray'};
  }
`;

const Label = styled.label``;

const Select = styled.select`
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 14px;
  font-style: normal;
  font-variant: normal;
  font-weight: 400;
  line-height: 30px;
`;

const Option = styled.option``;

const Error = styled.div`
  cursor: pointer;
  color: white;
  background-color: crimson;
`;

const SearchDiv = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: end;

  height: 20vh;
  flex-shrink: 0;
  flex-grow: 0;
  margin: 2px;

  @media (hover: none) and (max-width: 480px) {
    width: 100vw;
    height: auto;
  }
`;

const InputText = styled.input`
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 14px;
  font-style: normal;
  font-variant: normal;
  font-weight: 400;
  line-height: 30px;
`;

const InputButton = styled.input`
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 14px;
  font-style: normal;
  font-variant: normal;
  font-weight: 400;
  line-height: 30px;
  height: 36px;
  cursor: pointer;
`;

const SearchInfo = styled.div`
  flex-shrink: 0;
  margin: 2px;
  overflow: auto;

  @media (hover: none) and (max-width: 480px) {
    width: 100vw;
  }
`;

type ResultsProps = {
  isLoading: boolean;
};

const Results = styled.div<ResultsProps>`
  overflow: auto;
  flex-grow: 1;

  filter: ${({ isLoading }) =>
    isLoading ? 'brightness(0.8) blur(5px)' : 'none'};

  @media (hover: none) and (max-width: 480px) {
    width: 100vw;
  }
`;

const Hit = styled.div`
  padding: 4px 8px;
  margin: 2px;
  border: 1px solid black;
`;

const HitInfo = styled.div`
  font-weight: bolder;
`;

const HitSnippet = styled.div`
  max-height: 5em;
  overflow: auto;
  background-color: khaki;
  padding: 2px;
  margin: 2px;
  line-height: 1.2em;
  margin-left: 20px;
`;

const PaginationDiv = styled.div`
  margin-top: 2px;
  padding-top: 2px;
  flex-grow: 0;
  flex-shrink: 1;

  @media (hover: none) and (max-width: 480px) {
    width: 100vw;
  }
`;

type PaginationProps = {
  'isCurrent': boolean;
  'isDotDotDot': boolean;
  'data-page': number;
};

function styleCurrentPaginationElem(isCurrent: boolean) {
  if (!isCurrent) {
    return css``;
  }
  return css`
    user-select: none;
    cursor: inherit;
    font-weight: bolder;
    background-color: lightgray;

    &:hover {
      background-color: lightgray;
    }
  `;
}

function styleDotDotDotPaginationElem(isDotDotDot: boolean) {
  if (!isDotDotDot) {
    return css``;
  }
  return css`
    user-select: none;
    cursor: inherit;
    background-color: inherit;

    &:hover {
      background-color: inherit;
    }
  `;
}

const Pagination = styled.span<PaginationProps>`
  display: inline-block;
  padding: 5px 10px;
  cursor: pointer;

  &:hover {
    background-color: silver;
  }

  ${({ isCurrent }) => styleCurrentPaginationElem(isCurrent)}

  ${({ isDotDotDot }) => styleDotDotDotPaginationElem(isDotDotDot)}
`;

interface SearchProps extends ConnectSearch {
  apiActions: ApiActions;
  userId: string | undefined;
  ready: boolean;
  dbs: DBName[];
}

type EmptySearchProps = {
  ready: false;
  query: '';
  filters: SearchFilters;
  page: 0;
};

type SearchState = {
  stats: Stats;
  results: SearchResult;
  groups: { [key: string]: boolean };
  isLoading: boolean;
  isAdding: boolean;
  documentMessage: string;
};

class Search extends PureComponent<SearchProps, SearchState> {
  private readonly queryRef: React.RefObject<HTMLInputElement>;

  constructor(props: Readonly<SearchProps>) {
    super(props);
    this.state = {
      stats: {
        count: 0,
        fields: {},
      },
      results: {
        hits: [],
        status: '',
      },
      groups: {},
      isLoading: false,
      isAdding: false,
      documentMessage: '',
    };
    this.queryRef = React.createRef();
  }

  componentDidMount(): void {
    this.componentDidUpdate(
      { ready: false, filters: {}, query: '', page: 0 },
      undefined,
    );
  }

  componentDidUpdate(
    prevProps: Readonly<SearchProps> | EmptySearchProps,
    _prevState: Readonly<SearchState> | undefined,
  ): void {
    const {
      ready: oldReady,
      filters: oldFilters,
      query: oldQuery,
      page: oldPage,
    } = prevProps;
    const { ready, db, filters, query, page, apiActions } = this.props;
    if (!ready) {
      return;
    }
    const forceUpdate = ready !== oldReady;
    if (forceUpdate || filters !== oldFilters) {
      apiActions.stats(db, filters, this.setStats);
    }
    if (
      forceUpdate ||
      query !== oldQuery ||
      page !== oldPage ||
      filters !== oldFilters
    ) {
      this.setState(
        {
          isLoading: true,
        },
        () => apiActions.search(query, db, filters, page, this.setResults),
      );
    }
  }

  setStats = (stats: Stats) => {
    this.setState({
      stats,
    });
  };

  setResults = (results: SearchResult) => {
    this.setState({
      results,
      isLoading: false,
    });
  };

  onDBChange: ChangeEventHandler<HTMLSelectElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { dbs, db, query, dispatch } = this.props;
    const target = e.currentTarget;
    const newDB = target.value as DBName;
    if (!dbs.includes(newDB) || newDB === db) {
      return;
    }
    dispatch(
      setSearch({
        db: newDB,
        query,
        filters: {},
        page: 0,
      }),
    );
  };

  clickGroup: MouseEventHandler<HTMLDivElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { groups } = this.state;
    const groupName = e.currentTarget.getAttribute('data-group');
    if (!groupName) {
      return;
    }
    this.setState({
      groups: {
        ...groups,
        [groupName]: !groups[groupName],
      },
    });
  };

  clickField: MouseEventHandler<HTMLLIElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { dispatch, db, query, filters } = this.props;
    const target = e.currentTarget;
    const field = target.getAttribute('data-field');
    const groupName = target.getAttribute('data-group');
    if (!field || !groupName) {
      return;
    }
    let newFilter = [...(filters[groupName] ?? [])];
    if (newFilter.includes(field)) {
      newFilter = newFilter.filter((f) => f !== field);
    } else {
      newFilter = [...newFilter, field];
    }
    dispatch(
      setSearch({
        db,
        query,
        filters: Object.fromEntries(
          Object.entries({
            ...filters,
            [groupName]: newFilter,
          }).filter(([_, vals]) => vals.length),
        ),
        page: 0,
      }),
    );
  };

  clickPage: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { dispatch, db, query, filters } = this.props;
    const target = e.currentTarget;
    const page = target.getAttribute('data-page');
    if (page === null) {
      return;
    }
    dispatch(
      setSearch({
        db,
        query,
        filters,
        page: +page,
      }),
    );
  };

  clickError: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { dispatch, db, query, filters, page } = this.props;
    dispatch(
      setSearch({
        db,
        query,
        filters: { ...filters },
        page,
      }),
    );
  };

  clickAddAll: MouseEventHandler<HTMLInputElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { apiActions, collectionId } = this.props;
    const {
      isAdding,
      results: { hits },
    } = this.state;
    const mainIds = hits.map(({ mainId }) => mainId);
    if (isAdding || collectionId < 0 || !mainIds.length) {
      this.setState({
        documentMessage: '',
      });
      return;
    }
    this.setState(
      {
        isAdding: true,
        documentMessage: '',
      },
      () => {
        apiActions.addDocuments(collectionId, mainIds, (newDocs) => {
          this.setState({
            isAdding: false,
            documentMessage: `Added ${newDocs} new documents!`,
          });
        });
      },
    );
  };

  keyDownInput: KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    if (e.key !== 'Enter' || e.shiftKey) {
      return;
    }
    e.preventDefault();
    const target = e.currentTarget;
    const { dispatch, db, filters } = this.props;
    dispatch(
      setSearch({
        db,
        query: target.value,
        filters: { ...filters },
        page: 0,
      }),
    );
  };

  results(): ReactNode {
    const {
      results: { hits },
    } = this.state;
    const currentUrl = window.location.href;
    return (
      <React.Fragment>
        {hits.map(
          ({
            url,
            title,
            mainId,
            score,
            meta: { date, iso3, language },
            snippets,
          }) => {
            const params = new URLSearchParams(
              new URL(currentUrl).searchParams,
            );
            params.set('q', `=${mainId}`);
            const link = new URL(window.location.href);
            link.search = params.toString();
            return (
              <Hit key={mainId}>
                <a href={url}>{title}</a>
                <HitInfo>
                  <a href={`${link}`}>{mainId}</a> score: {score} date: {date}
                </HitInfo>
                <div>
                  countries: {(iso3 ?? []).join(', ')} languages:{' '}
                  {(language ?? []).join(', ')}
                </div>
                <div>
                  {snippets.map((snippet, ix) => (
                    <HitSnippet key={ix}>{snippet}</HitSnippet>
                  ))}
                </div>
              </Hit>
            );
          },
        )}
      </React.Fragment>
    );
  }

  pagination(currentPage: number, pageCount: number): ReactNode {
    return Array.from(Array(pageCount).keys())
      .map((page) => ({
        page: currentPage > MID_PAGE ? page + currentPage - MID_PAGE : page,
        isFirst: page === 0,
        isLast: page >= DISPLAY_PAGE_COUNT,
      }))
      .map(({ page, isFirst, isLast }) => {
        const isCurrent = page === currentPage;
        const isDotDotDot = isLast || (currentPage > MID_PAGE && isFirst);
        return (
          <Pagination
            key={`page-${page}`}
            isCurrent={isCurrent}
            isDotDotDot={isDotDotDot}
            data-page={page}
            onClick={!isCurrent && !isDotDotDot ? this.clickPage : undefined}>
            {currentPage > MID_PAGE
              ? isFirst || isLast
                ? '...'
                : `${page}`
              : isLast
              ? '...'
              : `${page}`}
          </Pagination>
        );
      });
  }

  renderStats() {
    const { filters } = this.props;
    const { stats, groups } = this.state;
    const { count, fields } = stats;
    if (count !== undefined && count < 0) {
      return (
        <Error onClick={this.clickError}>
          An error occurred! Click here to try again.
        </Error>
      );
    }
    return Object.keys(fields)
      .filter((field) => !['date', 'base'].includes(field))
      .map((field) => {
        const isGroupSelected = groups[field];
        return (
          <Field
            key={`group-${field}`}
            data-group={field}
            onClick={this.clickGroup}>
            <FieldName
              isGroupSelected={isGroupSelected}>{`${field}`}</FieldName>
            {isGroupSelected ? (
              <FieldUl isGroupSelected={isGroupSelected}>
                {Object.keys(fields[field]).map((fieldValue) => {
                  const isFieldSelected = (filters[field] ?? []).includes(
                    fieldValue,
                  );
                  const fieldName = `field-${field}-${fieldValue}`;
                  return (
                    <FieldLi
                      key={fieldName}
                      isFieldSelected={isFieldSelected}
                      onClick={this.clickField}
                      data-field={fieldValue}
                      data-group={field}>
                      {fieldValue} ({fields[field][fieldValue]})
                    </FieldLi>
                  );
                })}
              </FieldUl>
            ) : null}
          </Field>
        );
      });
  }

  render(): ReactNode {
    const {
      dbs,
      db,
      page,
      query,
      apiActions,
      collectionId,
      userId,
      collectionUser,
    } = this.props;
    const {
      stats: { count },
      isLoading,
      results: { status },
      isAdding,
      documentMessage,
    } = this.state;
    const pageCount = Math.min(
      Math.ceil((count ?? 0) / PAGE_SIZE),
      DISPLAY_PAGE_COUNT + 1,
    );
    return (
      <React.Fragment>
        <VSide>
          <TopLeft>
            <Label>
              Database:{' '}
              <Select
                onChange={this.onDBChange}
                value={db}>
                {dbs.map((db) => (
                  <Option
                    key={db}
                    value={db}>
                    {db}
                  </Option>
                ))}
              </Select>
            </Label>
            {userId ? (
              <React.Fragment>
                <Collections
                  apiActions={apiActions}
                  userId={userId}
                  canCreate={true}
                  isCmp={false}
                  isHorizontal={false}
                  isInline={false}
                />
                <InputButton
                  type="button"
                  onClick={this.clickAddAll}
                  value="Add Results to Collection"
                  disabled={
                    collectionId < 0 || isAdding || collectionUser !== userId
                  }
                />
                {documentMessage.length ? <div>{documentMessage}</div> : null}
              </React.Fragment>
            ) : null}
            {count !== undefined ? `Total documents: ${count}` : null}
          </TopLeft>
          <FilterDiv>{this.renderStats()}</FilterDiv>
        </VSide>
        <VMain>
          <SearchDiv>
            <InputText
              type="search"
              placeholder="Type a query..."
              autoFocus={true}
              autoComplete="off"
              onKeyDown={this.keyDownInput}
              defaultValue={query}
            />
          </SearchDiv>
          <SearchInfo>
            Status: {status && !isLoading ? status : 'pending'} Showing results
            for: {query}
          </SearchInfo>
          <Results isLoading={isLoading}>{this.results()}</Results>
          <PaginationDiv>{this.pagination(page, pageCount)}</PaginationDiv>
        </VMain>
      </React.Fragment>
    );
  }
} // Search

const connector = connect((state: RootState) => ({
  db: state.searchState.db,
  query: state.searchState.query,
  filters: state.searchState.filters,
  page: state.searchState.page,
  collectionId: state.collectionState.collectionId,
  collectionUser: state.collectionState.collectionUser,
}));

export default connector(Search);

type ConnectSearch = ConnectedProps<typeof connector>;
