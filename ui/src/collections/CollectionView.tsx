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
import { MouseEventHandler, PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import ApiActions from '../api/ApiActions';
import { DocumentObj } from '../api/types';
import { RootState } from '../store';
import Collections from './Collections';

type DocumentStats = {
  total: number;
  included: number;
  excluded: number;
  complete: number;
  errors: number;
};

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

  filter: ${({ isLoading }) =>
    isLoading ? 'brightness(0.8) blur(5px)' : 'none'};
`;

const MainSpace = styled.span`
  flex-grow: 1;
  display: inline-block;
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
`;

const DocumentLink = styled.a`
  display: inline-block;
  padding: 0 10px;
  width: 100%;
  color: inherit;
  background-color: white;
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
`;

const Output = styled.pre`
  font-family: 'Courier New', Courier, monospace;
  font-weight: 500;
  line-height: 15px;
  flex-grow: 1;
  white-space: pre-wrap;
  background-color: #ddd;
  height: fit-content;
  margin: 0;
`;

interface CollectionViewProps extends ConnectCollectionView {
  apiActions: ApiActions;
  isLoggedIn: boolean;
}

type EmptyCollectionViewProps = {
  collectionId: -1;
};

type CollectionViewState = {
  documents: DocumentObj[];
  selections: { [key: string]: string | undefined };
  fullText: { [key: string]: string };
  needsUpdate: boolean;
  isLoading: boolean;
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
    };
  }

  componentDidMount() {
    this.componentDidUpdate({ collectionId: -1 });
  }

  componentDidUpdate(
    prevProps: Readonly<CollectionViewProps> | EmptyCollectionViewProps,
  ) {
    const { collectionId: oldCollectionId } = prevProps;
    const { collectionId, apiActions } = this.props;
    if (collectionId !== oldCollectionId) {
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
          if (collectionId < 0) {
            this.setState({ documents: [], isLoading: false });
          } else {
            apiActions.documents(collectionId, (documents) => {
              const { collectionId: currentCollectionId } = this.props;
              if (collectionId === currentCollectionId) {
                this.setState({ documents, isLoading: false });
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
    apiActions.requeue(collectionId, mainIds, () => {
      this.setState({
        needsUpdate: true,
      });
    });
  };

  computeStats(): DocumentStats {
    const { documents } = this.state;
    return documents.reduce(
      (
        { total, included, excluded, complete, errors },
        { isValid, deepDiveResult, error },
      ) => {
        return {
          total: total + 1,
          included: included + (isValid === true ? 1 : 0),
          excluded: excluded + (isValid === false ? 1 : 0),
          complete: complete + (deepDiveResult ? 1 : 0),
          errors: errors + (error ? 1 : 0),
        };
      },
      {
        total: 0,
        included: 0,
        excluded: 0,
        complete: 0,
        errors: 0,
      },
    );
  }

  render() {
    const { isLoggedIn, apiActions } = this.props;
    if (!isLoggedIn) {
      return <VMain>You must be logged in to view collections!</VMain>;
    }
    const { documents, selections, fullText, isLoading } = this.state;
    const { total, included, excluded, complete, errors } =
      this.computeStats();
    return (
      <VMain>
        <Collections
          apiActions={apiActions}
          canCreate={true}
        />
        <MainStats isLoading={isLoading}>
          <span>Total: {total}</span>
          <span>Included: {included}</span>
          <span>Excluded: {excluded}</span>
          <span>Complete: {complete}</span>
          <span>Errors: {errors}</span>
          <MainSpace />
          <input
            type="button"
            value="Recompute All"
            onClick={this.clickRecomputeAll}
          />
        </MainStats>
        <Documents isLoading={isLoading}>
          {documents.map(
            ({
              mainId,
              url,
              title,
              isValid,
              verifyReason,
              deepDiveResult,
              error,
            }) => {
              const sel = selections[mainId];
              const content = fullText[mainId];
              const { reason: _, ...scores } = deepDiveResult ?? {};
              return (
                <Document key={mainId}>
                  <DocumentRow>
                    <DocumentLink href={url ?? '#'}>
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
                      color={deepDiveResult ? '#ccebc5' : 'white'}
                      active={!!deepDiveResult}
                      selected={sel === 'scores'}
                      onClick={deepDiveResult ? this.clickTab : undefined}>
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
                      {deepDiveResult ? (
                        <Output>{JSON.stringify(scores)}</Output>
                      ) : null}
                      {deepDiveResult ? (
                        <Output>{deepDiveResult.reason}</Output>
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
            },
          )}
        </Documents>
      </VMain>
    );
  }
} // CollectionView

const connector = connect((state: RootState) => ({
  collectionId: state.collectionState.collectionId,
}));

export default connector(CollectionView);

type ConnectCollectionView = ConnectedProps<typeof connector>;
