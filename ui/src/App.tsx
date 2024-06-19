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
import React, { MouseEventHandler, PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import styled from 'styled-components';
import ApiActions from './api/ApiActions';
import { SearchState } from './api/types';
import CollectionView from './collections/CollectionView';
import { LOGIN_URL } from './misc/constants';
import Search from './search/Search';
import { setSearch } from './search/SearchStateSlice';
import { RootState } from './store';

const HMain = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  max-width: 100vw;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
    align-items: start;
    flex-direction: column-reverse;
  }
`;

const VMain = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
  flex-grow: 1;
  height: 100vh;
  max-height: 100vh;
  max-width: 60vw;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
  }
`;

const UserDiv = styled.div`
  position: fixed;
  top: 0;
  right: 0;
  padding: 0;
  margin: 0;
  min-width: 100px;

  @media (hover: none) and (max-width: 480px) {
    position: static;
    margin: 0;
    width: 100vw;
  }
`;

type CollapseButtonProps = {
  isCollapsed: boolean;
};

const CollapseButton = styled.div<CollapseButtonProps>`
  width: 100%;
  cursor: pointer;
  text-align: center;
  border: ${({ isCollapsed }) => (isCollapsed ? '1px solid #ddd' : 'none')};
  border-top: 1px solid #ddd;
  border-bottom: 1px solid #ddd;
  background-color: ${({ isCollapsed }) => (isCollapsed ? '#eee' : 'white')};
  margin-top: -1px;
  margin-bottom: -1px;
  margin-right: 10px;

  &:hover {
    filter: brightness(0.8);
  }

  &:active {
    filter: brightness(0.85);
  }
`;

const NavRow = styled.a`
  display: block;
  width: 100%;
  cursor: pointer;
  background-color: white;
  border-top: 1px solid #ddd;
  border-bottom: 1px solid #ddd;
  padding: 5px;
  margin-top: -1px;
  margin-bottom: -1px;
  margin-right: 10px;
  text-decoration: none;

  &:hover {
    filter: brightness(0.8);
  }

  &:active {
    filter: brightness(0.85);
  }
`;

type AppProps = ConnectApp;

type AppState = {
  ready: boolean;
  userName: string | undefined;
  isCollapsed: boolean;
};

class App extends PureComponent<AppProps, AppState> {
  private readonly apiActions: ApiActions;

  constructor(props: AppProps) {
    super(props);
    this.state = { ready: false, userName: undefined, isCollapsed: false };
    this.apiActions = new ApiActions(undefined);

    window.addEventListener('popstate', (event) => {
      const { dispatch, query, filters, page } = this.props;
      const state: SearchState = event.state;
      const { q, filter, p } = state;
      let newQuery = query;
      let newFilters = filters;
      let newPage = page;
      if (q) {
        newQuery = q;
      }
      if (filter) {
        newFilters = JSON.parse(filter);
      }
      if (p || p === 0) {
        newPage = p;
      }
      dispatch(
        setSearch({ query: newQuery, filters: newFilters, page: newPage }),
      );
    });
  }

  componentDidMount(): void {
    const { dispatch } = this.props;
    const params = new URL(window.location.href).searchParams;
    const query = params.get('q');
    let newQuery = '';
    let newFilters = {};
    let newPage = 0;
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
    dispatch(
      setSearch({ query: newQuery, filters: newFilters, page: newPage }),
    );
  }

  componentDidUpdate(prevProps: Readonly<AppProps>): void {
    const { ready } = this.state;
    const { query, filters, page } = this.props;
    const {
      query: prevQuery,
      filters: prevFilters,
      page: prevPage,
    } = prevProps;
    if (!ready) {
      this.apiActions.user((userName) => {
        this.setState({ ready: true, userName });
      });
      return;
    }
    if (query !== prevQuery || filters !== prevFilters || page !== prevPage) {
      const history = window.history;
      const params = new URLSearchParams(
        new URL(window.location.href).searchParams,
      );
      if (query) {
        params.set('q', `${query}`);
      } else {
        params.delete('q');
      }
      const filterStr = JSON.stringify(filters, Object.keys(filters).sort());
      params.set('filter', filterStr);
      params.set('p', `${page}`);

      const url = new URL(window.location.href);
      url.search = params.toString();
      history.pushState({ q: query, filter: filterStr, p: page }, '', url);
    }
  }

  toggleCollapse: MouseEventHandler<HTMLDivElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { isCollapsed } = this.state;
    this.setState({
      isCollapsed: !isCollapsed,
    });
  };

  render() {
    const { ready, userName, isCollapsed } = this.state;
    const isLoggedIn = !!userName;
    return (
      <HMain>
        <BrowserRouter>
          <Routes>
            <Route
              path="/"
              element={
                <VMain>
                  <a href="/search">Semantic Search</a>
                  {isLoggedIn ? <a href="/collection">Collection</a> : null}
                </VMain>
              }
            />
            <Route
              path="/search"
              element={
                <Search
                  apiActions={this.apiActions}
                  isLoggedIn={isLoggedIn}
                  ready={ready}
                />
              }
            />
            <Route
              path="/collection"
              element={
                <CollectionView
                  apiActions={this.apiActions}
                  isLoggedIn={isLoggedIn}
                  visIsRelative={false}
                />
              }
            />
          </Routes>
        </BrowserRouter>
        <UserDiv>
          {isCollapsed ? null : (
            <React.Fragment>
              <NavRow
                href={
                  isLoggedIn
                    ? `${LOGIN_URL}`
                    : `${LOGIN_URL}?origin=${encodeURIComponent(
                        window.location.href,
                      )}`
                }>
                {isLoggedIn ? `Hello, ${userName}!` : 'Login'}
              </NavRow>
              <NavRow href="/search">Search</NavRow>
              {isLoggedIn ? (
                <NavRow href="/collection">Collection</NavRow>
              ) : null}
            </React.Fragment>
          )}
          <CollapseButton
            isCollapsed={isCollapsed}
            onClick={this.toggleCollapse}>
            {isCollapsed ? <span>&#x25BC;</span> : <span>&#x25B2;</span>}
          </CollapseButton>
        </UserDiv>
      </HMain>
    );
  }
} // App

const connector = connect((state: RootState) => ({
  query: state.searchState.query,
  filters: state.searchState.filters,
  page: state.searchState.page,
}));

export default connector(App);

type ConnectApp = ConnectedProps<typeof connector>;
