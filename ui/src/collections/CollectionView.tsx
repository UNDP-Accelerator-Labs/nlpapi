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
import styled from 'styled-components';
import ApiActions from '../api/ApiActions';
import {
  DocumentObj,
  DocumentStats,
  Filter,
  STAT_NAMES,
  StatNumbers,
} from '../api/types';
import SpiderGraph from '../misc/SpiderGraph';
import { RootState } from '../store';
import { setCurrentCollectionFilter } from './CollectionStateSlice';
import Collections from './Collections';

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
    height: auto;
    max-height: auto;
    max-width: 100vw;
  }
`;

const VSide = styled.div`
  display: flex;
  justify-content: start;
  flex-direction: column;
  flex-grow: 0;
  height: 100vh;
  max-height: 100vh;
  width: fit-content;

  @media (hover: none) and (max-width: 480px) {
    justify-content: start;
    height: auto;
    align-items: center;
    margin: 0;
    margin-top: 1px;
    width: 100vw;
  }
`;

const VBuffer = styled.div`
  height: 60px;

  @media (hover: none) and (max-width: 480px) {
    height: 0;
  }
`;

type DocumentsProps = {
  isLoading: boolean;
};

const Documents = styled.div<DocumentsProps>`
  flex-grow: 1;
  overflow: auto;

  filter: ${({ isLoading }) =>
    isLoading ? 'brightness(0.8) blur(5px)' : 'none'};

  @media (hover: none) and (max-width: 480px) {
    overflow: visible;
  }
`;

type MainStatsProps = {
  isLoading: boolean;
};

const MainStats = styled.div<MainStatsProps>`
  display: flex;
  flex-direction: row;
  flex-grow: 0;
  width: 100%;
  gap: 5px;
  border-bottom: 1px solid black;

  filter: ${({ isLoading }) =>
    isLoading ? 'brightness(0.8) blur(5px)' : 'none'};

  @media (hover: none) and (max-width: 480px) {
    flex-wrap: wrap;
  }
`;

const MainSpace = styled.span`
  flex-grow: 1;
  display: inline-block;

  @media (hover: none) and (max-width: 480px) {
    flex-grow: 0;
    width: 100vw;
  }
`;

const MainButton = styled.input`
  cursor: pointer;
  margin-bottom: -1px;

  @media (hover: none) and (max-width: 480px) {
    align-self: right;
  }
`;

type MainFilterProps = {
  'data-selector': Filter;
  'selected': Filter;
};

const MainFilter = styled.span<MainFilterProps>`
  display: inline-block;
  padding: 5px 10px;
  cursor: pointer;
  background-color: white;
  user-select: none;
  filter: ${({ selected, 'data-selector': tgt }) =>
    selected === tgt ? 'brightness(0.8)' : 'none'};

  &:hover {
    filter: brightness(0.8);
  }

  &:active {
    filter: brightness(0.85);
  }
`;

const Document = styled.div`
  display: flex;
  flex-direction: column;
  border: 1px silver solid;
  margin: -1px 0;
  height: 300px;

  &:first-child {
    margin-top: 0;
  }

  &:last-child {
    margin-bottom: 0;
  }

  &:nth-child(even) {
    background-color: #eee;
  }

  @media (hover: none) and (max-width: 480px) {
    height: auto;
  }
`;

const DocumentLink = styled.a`
  display: inline-block;
  padding: 0 10px;
  width: 100%;
  color: inherit;
  background-color: #decbe4;
  text-decoration: none;
  filter: none;

  &:visited {
    color: inherit;
  }

  &:hover,
  &:focus {
    filter: brightness(80%);
  }

  &:active {
    filter: brightness(85%);
  }
`;

const DocumentRow = styled.div`
  flex-shrink: 0;
  flex-grow: 0;
`;

const DocumentTabList = styled.div`
  display: flex;
  flex-direction: row;
`;

const TabSpace = styled.span`
  flex-grow: 1;
  display: inline-block;
  margin: 0;
  border: 1px silver dotted;
  background-color: white;
`;

type DocumentTabProps = {
  'data-main': string;
  'data-tab': string;
  'color'?: string;
  'active': boolean;
  'selected': boolean;
};

const DocumentTab = styled.span<DocumentTabProps>`
  flex-grow: 0;
  flex-shrink: 0;
  margin: 0 -1px;
  display: inline-block;
  padding: 0 10px;
  border: 1px silver dotted;
  cursor: ${({ active }) => (active ? 'pointer' : 'not-allowed')};
  background-color: ${({ color }) => (color ? color : 'white')};
  filter: ${({ selected }) => (selected ? 'brightness(80%)' : 'none')};
  user-select: none;

  &:first-child {
    border-left: 1px silver solid;
  }

  &:hover {
    filter: ${({ active }) => (active ? 'brightness(80%)' : 'none')};
  }

  &:active {
    filter: ${({ active }) => (active ? 'brightness(85%)' : 'none')};
  }

  @media (hover: none) and (max-width: 480px) {
    flex-wrap: wrap;
  }
`;

type DocumentTabButtonProps = {
  'data-main': string;
};

const DocumentTabButton = styled.span<DocumentTabButtonProps>`
  flex-grow: 0;
  flex-shrink: 0;
  margin: 0 -1px;
  display: inline-block;
  padding: 0 10px;
  border: 1px silver dotted;
  cursor: pointer;
  background-color: white;
  filter: none;
  user-select: none;

  &:last-child {
    border-right: 1px silver solid;
  }

  &:hover {
    filter: brightness(80%);
  }

  &:active {
    filter: brightness(85%);
  }
`;

const DocumentBody = styled.div`
  display: flex;
  flex-direction: row;
  flex-grow: 1;
  overflow: auto;

  @media (hover: none) and (max-width: 480px) {
    flex-wrap: wrap;
    height: 300px;
  }
`;

const OutputDiv = styled.div`
  flex-grow: 1;
  flex-shrink: 1;
  min-width: fit-content;
  text-align: right;
  padding: 5px;
`;

const Output = styled.pre`
  flex-grow: 1;
  flex-shrink: 1;
  font-family: 'Courier New', Courier, monospace;
  font-weight: 500;
  line-height: 15px;
  white-space: pre-wrap;
  background-color: #ddd;
  height: fit-content;
  margin: 0;
`;

interface CollectionViewProps extends ConnectCollectionView {
  apiActions: ApiActions;
  isLoggedIn: boolean;
  visIsRelative: boolean;
}

type EmptyCollectionViewProps = {
  collectionId: -1;
  isLoggedIn: boolean;
};

type CollectionViewState = {
  documents: DocumentObj[];
  selections: { [key: string]: string | undefined };
  fullText: { [key: string]: string };
  needsUpdate: boolean;
  isLoading: boolean;
  allScores: StatNumbers;
};

class CollectionView extends PureComponent<
  CollectionViewProps,
  CollectionViewState
> {
  constructor(props: Readonly<CollectionViewProps>) {
    super(props);
    this.state = {
      documents: [],
      selections: {},
      fullText: {},
      needsUpdate: true,
      isLoading: false,
      allScores: {},
    };
  }

  componentDidMount() {
    this.componentDidUpdate({ collectionId: -1, isLoggedIn: false });
  }

  componentDidUpdate(
    prevProps: Readonly<CollectionViewProps> | EmptyCollectionViewProps,
  ) {
    const { collectionId: oldCollectionId, isLoggedIn: oldIsLoggedIn } =
      prevProps;
    const { collectionId, apiActions, isLoggedIn } = this.props;
    if (collectionId !== oldCollectionId || oldIsLoggedIn !== isLoggedIn) {
      this.setState({
        needsUpdate: true,
      });
    }
    const { needsUpdate, selections, fullText } = this.state;
    if (needsUpdate) {
      this.setState(
        {
          needsUpdate: false,
          isLoading: true,
        },
        () => {
          if (collectionId < 0 || !isLoggedIn) {
            this.setState({ documents: [], isLoading: false, allScores: {} });
          } else {
            apiActions.documents(collectionId, (documents) => {
              const { collectionId: currentCollectionId } = this.props;
              if (collectionId === currentCollectionId) {
                const allScores = this.computeTotalScores(documents);
                this.setState({ documents, isLoading: false, allScores });
              }
            });
          }
        },
      );
    }
    let modified = false;
    const newFullText = { ...fullText };
    Object.keys(selections)
      .filter(
        (mainId) =>
          selections[mainId] === 'fulltext' && fullText[mainId] === undefined,
      )
      .forEach((mainId) => {
        modified = true;
        newFullText[mainId] = '[retrieving...]';
        apiActions.getFulltext(mainId, (mainId, content, error) => {
          const { fullText } = this.state;
          const err = error ? `\nERROR: ${error}` : '';
          this.setState({
            fullText: {
              ...fullText,
              [mainId]: `${content ?? ''}${err}`,
            },
          });
        });
      });
    if (modified) {
      this.setState({
        fullText: newFullText,
      });
    }
  }

  clickTab: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const target = e.currentTarget;
    const mainId = target.getAttribute('data-main');
    const tab = target.getAttribute('data-tab');
    if (!mainId || !tab) {
      return;
    }
    const { selections } = this.state;
    this.setState({
      selections: {
        ...selections,
        [mainId]: tab,
      },
    });
  };

  clickRecompute: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const target = e.currentTarget;
    const mainId = target.getAttribute('data-main');
    if (!mainId) {
      return;
    }
    const { apiActions, collectionId } = this.props;
    if (collectionId < 0) {
      return;
    }
    apiActions.requeue(collectionId, [mainId], () => {
      this.setState({
        needsUpdate: true,
      });
    });
  };

  clickRecomputeAll: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { apiActions, collectionId } = this.props;
    const { documents } = this.state;
    const mainIds = documents.map(({ mainId }) => mainId);
    if (collectionId < 0 || !mainIds.length) {
      return;
    }
    const ma = `Are you sure you want to requeue ${mainIds.length} documents?`;
    const mb = 'All previous results will be discarded!';
    if (!window.confirm(`${ma} ${mb}`)) {
      return;
    }
    apiActions.requeue(collectionId, mainIds, () => {
      this.setState({
        needsUpdate: true,
      });
    });
  };

  clickRefresh: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    this.setState({ needsUpdate: true });
  };

  clickFilter: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const target = e.currentTarget;
    const filterValue = target.getAttribute('data-selector');
    if (!filterValue) {
      return;
    }
    const { dispatch } = this.props;
    dispatch(
      setCurrentCollectionFilter({ collectionFilter: filterValue as Filter }),
    );
  };

  isType(doc: DocumentObj, filter: Filter): boolean {
    const { isValid, deepDiveReason, error } = doc;
    if (filter === 'total') {
      return true;
    }
    if (filter === 'pending' && isValid === undefined && !error) {
      return true;
    }
    if (filter === 'included' && isValid === true) {
      return true;
    }
    if (filter === 'excluded' && isValid === false) {
      return true;
    }
    if (filter === 'complete' && isValid === true && deepDiveReason) {
      return true;
    }
    if (filter === 'errors' && error) {
      return true;
    }
    return false;
  }

  typeNum(doc: DocumentObj): number {
    const { isValid, deepDiveReason, error } = doc;
    if (error) {
      return 3;
    }
    if (isValid === undefined) {
      return 5;
    }
    if (isValid === true && deepDiveReason) {
      return 1;
    }
    if (isValid === false) {
      return 2;
    }
    if (isValid === true) {
      return 0;
    }
    return 4;
  }

  typeSelection(doc: DocumentObj): string | undefined {
    const { isValid, deepDiveReason, error } = doc;
    if (error) {
      return 'error';
    }
    if (isValid === undefined) {
      return undefined;
    }
    if (isValid === false) {
      return 'verify';
    }
    return deepDiveReason ? 'scores' : 'verify';
  }

  compareDocs = (a: DocumentObj, b: DocumentObj): number => {
    const aNum = this.typeNum(a);
    const bNum = this.typeNum(b);
    if (aNum === bNum) {
      return a.id - b.id;
    }
    return aNum - bNum;
  };

  computeStats(): DocumentStats {
    const { documents } = this.state;
    return documents.reduce(
      (p, doc) =>
        Object.fromEntries(
          Object.entries(p).map(([key, value]) => [
            key as Filter,
            value + (this.isType(doc, key as Filter) ? 1 : 0),
          ]),
        ) as DocumentStats,
      {
        total: 0,
        pending: 0,
        included: 0,
        excluded: 0,
        complete: 0,
        errors: 0,
      },
    );
  }

  computeTotalScores(docs: DocumentObj[]): StatNumbers {
    const { visIsRelative } = this.props;
    const keys = Array.from(
      docs.reduce(
        (p, { scores }) =>
          Object.keys(scores).reduce((sp, key) => sp.add(key), p),
        new Set<string>(),
      ),
    );
    const maxs = docs.reduce(
      (p, { scores }) => [
        ...p,
        Object.keys(scores).reduce(
          (m, mKey) => Math.max(m, +(scores[mKey] ?? 0)),
          0,
        ),
      ],
      [] as number[],
    );
    const count = maxs.reduce((p, maxValue) => p + (maxValue > 0 ? 1 : 0));
    return docs.reduce((p, { scores }, ix) => {
      const total = Math.max(visIsRelative ? maxs[ix] : count, 1);
      return Object.fromEntries(
        keys.map((key) => [key, p[key] + +(scores[key] ?? 0) / total]),
      );
    }, Object.fromEntries(keys.map((key) => [key, 0])));
  }

  render() {
    const { isLoggedIn, apiActions, visIsRelative, collectionFilter } =
      this.props;
    if (!isLoggedIn) {
      return <VMain>You must be logged in to view collections!</VMain>;
    }
    const { documents, selections, fullText, isLoading, allScores } =
      this.state;
    const stats = this.computeStats();
    return (
      <React.Fragment>
        <VMain>
          <Collections
            apiActions={apiActions}
            canCreate={true}
          />
          <MainStats isLoading={isLoading}>
            {Object.entries(stats).map(([sKey, sValue]) => (
              <MainFilter
                key={sKey as Filter}
                data-selector={sKey as Filter}
                selected={collectionFilter}
                onClick={this.clickFilter}>
                {STAT_NAMES[sKey as Filter]}: {sValue}
              </MainFilter>
            ))}
            <MainSpace />
            <MainButton
              type="button"
              value="Refresh"
              onClick={this.clickRefresh}
            />
            <MainButton
              type="button"
              value="Recompute All"
              onClick={this.clickRecomputeAll}
            />
          </MainStats>
          <Documents isLoading={isLoading}>
            {documents
              .filter((doc) => this.isType(doc, collectionFilter))
              .toSorted(this.compareDocs)
              .map((doc) => {
                const {
                  mainId,
                  url,
                  title,
                  isValid,
                  verifyReason,
                  deepDiveReason,
                  scores,
                  error,
                } = doc;
                const sel = selections[mainId] ?? this.typeSelection(doc);
                const content = fullText[mainId];
                return (
                  <Document key={mainId}>
                    <DocumentRow>
                      <DocumentLink
                        href={url ?? '#'}
                        target="_blank">
                        [{mainId}] {title}
                      </DocumentLink>
                    </DocumentRow>
                    <DocumentTabList>
                      <DocumentTab
                        data-main={mainId}
                        data-tab="verify"
                        color={
                          isValid === undefined
                            ? 'white'
                            : isValid
                            ? '#ccebc5'
                            : '#fed9a6'
                        }
                        active={isValid !== undefined}
                        selected={sel === 'verify'}
                        onClick={
                          isValid !== undefined ? this.clickTab : undefined
                        }>
                        Verify:{' '}
                        {isValid === undefined
                          ? error
                            ? 'error'
                            : 'pending'
                          : isValid
                          ? 'ok'
                          : 'excluded'}
                      </DocumentTab>
                      <DocumentTab
                        data-main={mainId}
                        data-tab="scores"
                        color={deepDiveReason ? '#ccebc5' : 'white'}
                        active={!!deepDiveReason}
                        selected={sel === 'scores'}
                        onClick={deepDiveReason ? this.clickTab : undefined}>
                        Scores
                      </DocumentTab>
                      <DocumentTab
                        data-main={mainId}
                        data-tab="fulltext"
                        color="white"
                        active={true}
                        selected={sel === 'fulltext'}
                        onClick={this.clickTab}>
                        Full-Text
                      </DocumentTab>
                      {error ? (
                        <DocumentTab
                          data-main={mainId}
                          data-tab="error"
                          color="#fbb4ae"
                          active={true}
                          selected={sel === 'error'}
                          onClick={this.clickTab}>
                          Error
                        </DocumentTab>
                      ) : null}
                      <TabSpace />
                      <DocumentTabButton
                        data-main={mainId}
                        onClick={this.clickRecompute}>
                        Recompute
                      </DocumentTabButton>
                    </DocumentTabList>
                    {sel === 'verify' ? (
                      <DocumentBody>
                        <Output>{verifyReason}</Output>
                      </DocumentBody>
                    ) : null}
                    {sel === 'scores' ? (
                      <DocumentBody>
                        {deepDiveReason ? (
                          <OutputDiv>
                            <SpiderGraph
                              stats={scores}
                              cmpStats={allScores}
                              isRelative={visIsRelative}
                            />
                          </OutputDiv>
                        ) : null}
                        {deepDiveReason ? (
                          <OutputDiv>
                            {Object.entries(scores)
                              .toSorted(([a], [b]) => a.localeCompare(b))
                              .map(([scoreKey, scoreValue]) => (
                                <p key={scoreKey}>
                                  {scoreKey}: {scoreValue}
                                </p>
                              ))}
                          </OutputDiv>
                        ) : null}
                        {deepDiveReason ? (
                          <Output>{deepDiveReason}</Output>
                        ) : null}
                      </DocumentBody>
                    ) : null}
                    {sel === 'fulltext' ? (
                      <DocumentBody>
                        <Output>{content}</Output>
                      </DocumentBody>
                    ) : null}
                    {sel === 'error' ? (
                      <DocumentBody>
                        <Output>{error}</Output>
                      </DocumentBody>
                    ) : null}
                  </Document>
                );
              })}
          </Documents>
        </VMain>
        <VSide>
          <VBuffer />
          <SpiderGraph
            stats={allScores}
            isRelative={visIsRelative}
          />
        </VSide>
      </React.Fragment>
    );
  }
} // CollectionView

const connector = connect((state: RootState) => ({
  collectionId: state.collectionState.collectionId,
  collectionFilter: state.collectionState.collectionFilter,
}));

export default connector(CollectionView);

type ConnectCollectionView = ConnectedProps<typeof connector>;
