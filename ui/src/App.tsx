import { PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import styled from 'styled-components';
import ApiActions from './api/ApiActions';
import { SearchState } from './api/types';
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

type AppProps = ConnectApp;

type AppState = {
  ready: boolean;
};

class App extends PureComponent<AppProps, AppState> {
  private readonly apiActions: ApiActions;

  constructor(props: AppProps) {
    super(props);
    this.state = { ready: false };
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
      this.setState({ ready: true });
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

  render() {
    const { ready } = this.state;
    return (
      <HMain>
        <BrowserRouter>
          <Routes>
            <Route
              path="/search"
              element={
                <Search
                  apiActions={this.apiActions}
                  ready={ready}
                />
              }
            />
          </Routes>
        </BrowserRouter>
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