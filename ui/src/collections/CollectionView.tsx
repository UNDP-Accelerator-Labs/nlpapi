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
  MouseEventHandler,
  PureComponent,
} from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import ApiActions from '../api/ApiActions';
import {
  DocumentObj,
  DocumentStats,
  Filter,
  STAT_NAMES,
  StatFull,
} from '../api/types';
import SpiderGraph from '../misc/SpiderGraph';
import { RootState } from '../store';
import { setCollectionFilter } from './CollectionStateSlice';
import Collections from './Collections';
import Document from './Document';
import TagFilter from './TagFilter';

const MAIN_COLOR = '#377eb8';
const CMP_COLOR = '#e41a1c';

type ColorBlockProps = {
  color: string;
};

const ColorBlock = styled.span<ColorBlockProps>`
  display: inline-block;
  background-color: ${({ color }) => color};
  border: 1px solid black;
  width: 1em;
  height: 1em;
  vertical-align: middle;
  transform: translate(0, -2px);
`;

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

const SideRow = styled.div`
  flex-shrink: 0;
  flex-grow: 0;
  margin-left: 5px;
  padding-left: 5px;
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

interface CollectionViewProps extends ConnectCollectionView {
  apiActions: ApiActions;
  userId: string | undefined;
}

type EmptyCollectionViewProps = {
  userId: string | undefined;
  collectionId: -1;
  collectionTag: null;
  cmpCollectionId: -1;
  cmpCollectionTag: null;
};

type CollectionViewState = {
  isReadonly: boolean;
  documents: DocumentObj[];
  cmpDocuments: DocumentObj[];
  needsUpdate: boolean;
  needsCmpUpdate: boolean;
  isLoading: boolean;
  allScores: StatFull;
  cmpScores: StatFull;
  visIsRelative: boolean;
};

type EmptyCollectionViewState = {
  visIsRelative: boolean;
};

class CollectionView extends PureComponent<
  CollectionViewProps,
  CollectionViewState
> {
  constructor(props: Readonly<CollectionViewProps>) {
    super(props);
    this.state = {
      isReadonly: true,
      documents: [],
      cmpDocuments: [],
      needsUpdate: true,
      needsCmpUpdate: true,
      isLoading: false,
      allScores: {},
      cmpScores: {},
      visIsRelative: false,
    };
  }

  componentDidMount() {
    this.componentDidUpdate(
      {
        userId: undefined,
        collectionId: -1,
        collectionTag: null,
        cmpCollectionId: -1,
        cmpCollectionTag: null,
      },
      {
        visIsRelative: false,
      },
    );
  }

  componentDidUpdate(
    prevProps: Readonly<CollectionViewProps> | EmptyCollectionViewProps,
    prevState: Readonly<CollectionViewState> | EmptyCollectionViewState,
  ) {
    const {
      userId: prevUserId,
      collectionId: prevCollectionId,
      collectionTag: prevCollectionTag,
      cmpCollectionId: prevCmpCollectionId,
      cmpCollectionTag: prevCmpCollectionTag,
    } = prevProps;
    const {
      collectionId,
      apiActions,
      userId,
      collectionTag,
      cmpCollectionId,
      cmpCollectionTag,
    } = this.props;
    if (collectionId !== prevCollectionId || prevUserId !== userId) {
      this.setState({
        needsUpdate: true,
      });
    }
    if (cmpCollectionId !== prevCmpCollectionId || prevUserId !== userId) {
      this.setState({
        needsCmpUpdate: true,
      });
    }
    const { visIsRelative: prevVisIsRelative } = prevState;
    const {
      needsUpdate,
      needsCmpUpdate,
      documents,
      cmpDocuments,
      visIsRelative,
    } = this.state;
    // main docs
    if (needsUpdate) {
      this.setState(
        {
          needsUpdate: false,
          isLoading: true,
        },
        () => {
          if (collectionId < 0 || !userId) {
            this.setState({
              isReadonly: true,
              documents: [],
              isLoading: false,
              allScores: {},
            });
          } else {
            apiActions.documents(collectionId, (documents, isReadonly) => {
              const { collectionId: currentCollectionId, collectionTag } =
                this.props;
              if (collectionId === currentCollectionId) {
                const allScores = this.computeTotalScores(
                  documents,
                  collectionTag,
                );
                this.setState({
                  isReadonly,
                  documents,
                  isLoading: false,
                  allScores,
                });
              }
            });
          }
        },
      );
    }
    if (
      collectionTag !== prevCollectionTag ||
      visIsRelative !== prevVisIsRelative
    ) {
      const allScores = this.computeTotalScores(documents, collectionTag);
      this.setState({ allScores });
    }
    // cmp docs
    if (needsCmpUpdate) {
      this.setState(
        {
          needsCmpUpdate: false,
        },
        () => {
          if (cmpCollectionId < 0 || !userId) {
            this.setState({
              cmpDocuments: [],
              cmpScores: {},
            });
          } else {
            apiActions.documents(cmpCollectionId, (cmpDocuments) => {
              const {
                cmpCollectionId: currentCmpCollectionId,
                cmpCollectionTag,
              } = this.props;
              if (cmpCollectionId === currentCmpCollectionId) {
                const cmpScores = this.computeTotalScores(
                  cmpDocuments,
                  cmpCollectionTag,
                );
                this.setState({ cmpDocuments, cmpScores });
              }
            });
          }
        },
      );
    }
    if (
      cmpCollectionTag !== prevCmpCollectionTag ||
      visIsRelative !== prevVisIsRelative
    ) {
      const cmpScores = this.computeTotalScores(
        cmpDocuments,
        cmpCollectionTag,
      );
      this.setState({ cmpScores });
    }
  }

  requestUpdate = () => {
    this.setState({ needsUpdate: true });
  };

  clickRecomputeAll: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { apiActions, collectionId, collectionTag, collectionFilter } =
      this.props;
    const { documents } = this.state;
    const mainIds = documents
      .filter((doc) => this.isType(doc, collectionFilter))
      .filter(this.getFilterTagFn(collectionTag))
      .map(({ mainId }) => mainId);
    if (collectionId < 0 || !mainIds.length) {
      return;
    }
    const ma = `Are you sure you want to requeue ${mainIds.length} documents?`;
    const mb = 'All previous results will be discarded!';
    if (!window.confirm(`${ma} ${mb}`)) {
      return;
    }
    apiActions.requeue(
      collectionId,
      mainIds,
      false,
      collectionFilter === 'errors',
      () => {
        this.setState({
          needsUpdate: true,
        });
      },
    );
  };

  clickRefresh: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    this.setState({ needsUpdate: true });
  };

  clickVisIsRelative: ChangeEventHandler<HTMLInputElement> = () => {
    const { visIsRelative } = this.state;
    this.setState({ visIsRelative: !visIsRelative });
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
    dispatch(setCollectionFilter({ collectionFilter: filterValue as Filter }));
  };

  isType = (doc: DocumentObj, filter: Filter): boolean => {
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
  };

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

  compareDocs = (a: DocumentObj, b: DocumentObj): number => {
    const aNum = this.typeNum(a);
    const bNum = this.typeNum(b);
    if (aNum === bNum) {
      return -(a.id - b.id);
    }
    return aNum - bNum;
  };

  computeStats(
    allDocs: DocumentObj[],
    tagFilter: string | null,
  ): DocumentStats {
    const docs = allDocs.filter(this.getFilterTagFn(tagFilter));
    return docs.reduce(
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

  computeTotalScores(
    allDocs: DocumentObj[],
    tagFilter: string | null,
  ): StatFull {
    const docs = allDocs.filter(({ tag }) => !tagFilter || tag === tagFilter);
    if (!docs.length) {
      return {};
    }
    // FIXME make use of visIsRelative
    // const { visIsRelative } = this.state;
    const keys = Array.from(
      docs.reduce(
        (p, { scores }) =>
          Object.keys(scores).reduce((sp, key) => sp.add(key), p),
        new Set<string>(),
      ),
    );
    const denoms = docs.reduce(
      (p, { scores }) => [
        ...p,
        Object.keys(scores).reduce((m, mKey) => m + +(scores[mKey] ?? 0), 0),
      ],
      [] as number[],
    );
    const count = denoms.reduce((p, denom) => p + (denom > 0 ? 1 : 0));
    const means = docs.reduce((p, { scores }) => {
      const total = Math.max(count, 1);
      return Object.fromEntries(
        keys.map((key) => [key, p[key] + +(scores[key] ?? 0) / total]),
      );
    }, Object.fromEntries(keys.map((key) => [key, 0])));
    const sq = (num: number) => num * num;
    const sampleStddev = docs.reduce((p, { scores }) => {
      const total = Math.max(count - 1, 1); // NOTE: sample Stddev is `n - 1`
      return Object.fromEntries(
        keys.map((key) => [
          key,
          p[key] + sq(+(scores[key] ?? 0) - means[key]) / total,
        ]),
      );
    }, Object.fromEntries(keys.map((key) => [key, 0])));
    return Object.fromEntries(
      keys.map((key) => [
        key,
        {
          mean: means[key] ?? 0,
          count,
          stddev: Math.sqrt(sampleStddev[key] ?? 0),
        },
      ]),
    );
  }

  getFilterTagFn =
    (collectionTag: string | null) =>
    ({ tag }: DocumentObj): boolean =>
      !collectionTag || tag === collectionTag;

  render() {
    const {
      userId,
      apiActions,
      collectionId,
      collectionName,
      collectionFilter,
      collectionTag,
    } = this.props;
    if (!userId) {
      return <VMain>You must be logged in to view collections!</VMain>;
    }
    const {
      documents,
      cmpDocuments,
      isLoading,
      allScores,
      cmpScores,
      isReadonly,
      visIsRelative,
    } = this.state;
    const stats = this.computeStats(documents, collectionTag);
    return (
      <React.Fragment>
        <VMain>
          <Collections
            apiActions={apiActions}
            userId={userId}
            canCreate={true}
            isCmp={false}
            isHorizontal={true}
            isInline={false}
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
            {!isReadonly ? (
              <React.Fragment>
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
              </React.Fragment>
            ) : null}
          </MainStats>
          <Documents isLoading={isLoading}>
            {documents
              .filter((doc) => this.isType(doc, collectionFilter))
              .filter(this.getFilterTagFn(collectionTag))
              .toSorted(this.compareDocs)
              .map((doc) => (
                <Document
                  key={doc.mainId}
                  doc={doc}
                  collectionId={collectionId}
                  allScores={allScores}
                  visIsRelative={visIsRelative}
                  apiActions={apiActions}
                  isReadonly={isReadonly}
                  requestUpdate={this.requestUpdate}
                />
              ))}
          </Documents>
        </VMain>
        <VSide>
          <VBuffer />
          <SideRow>
            <SpiderGraph
              stats={allScores}
              isRelative={visIsRelative}
              color={MAIN_COLOR}
              cmpColor={CMP_COLOR}
              cmpStats={cmpScores}
              showCmpCircles={true}
            />
          </SideRow>
          <SideRow>
            <ColorBlock color={MAIN_COLOR} /> Collection:{' '}
            {collectionName ?? '-'}
          </SideRow>
          <SideRow>
            <TagFilter
              documents={documents}
              isCmp={false}
              isType={this.isType}
            />
          </SideRow>
          <SideRow>
            <ColorBlock color={CMP_COLOR} />{' '}
            <Collections
              apiActions={apiActions}
              userId={userId}
              canCreate={false}
              isCmp={true}
              isHorizontal={false}
              isInline={true}
            />
          </SideRow>
          <SideRow>
            <TagFilter
              documents={cmpDocuments}
              isCmp={true}
              isType={this.isType}
            />
          </SideRow>
          <SideRow>
            <label>
              Normalize Article Contribution{' '}
              <input
                type="checkbox"
                checked={visIsRelative}
                onChange={this.clickVisIsRelative}
              />
            </label>
          </SideRow>
        </VSide>
      </React.Fragment>
    );
  }
} // CollectionView

const connector = connect((state: RootState) => ({
  collectionId: state.collectionState.collectionId,
  collectionName: state.collectionState.collectionName,
  collectionFilter: state.collectionState.collectionFilter,
  collectionTag: state.collectionState.collectionTag,
  cmpCollectionId: state.collectionState.cmpCollectionId,
  cmpCollectionTag: state.collectionState.cmpCollectionTag,
}));

export default connector(CollectionView);

type ConnectCollectionView = ConnectedProps<typeof connector>;
