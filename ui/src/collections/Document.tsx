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
import styled from 'styled-components';
import ApiActions from '../api/ApiActions';
import { DocumentObj, StatNumbers } from '../api/types';
import SpiderGraph from '../misc/SpiderGraph';

type Tab = 'tag' | 'verify' | 'scores' | 'error' | 'fulltext';

const DocumentDiv = styled.div`
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
  'data-tab': Tab;
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

const DocumentTabButton = styled.span`
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

type DocumentProps = {
  apiActions: ApiActions;
  isReadonly: boolean;
  doc: DocumentObj;
  collectionId: number;
  allScores: StatNumbers;
  visIsRelative: boolean;
  requestUpdate: () => void;
};

type DocumentState = {
  sel: Tab | undefined;
  fullText: string | undefined;
  fullTextNum: number;
};

type EmptyDocumentState = {
  sel: undefined;
};

export default class Document extends PureComponent<
  DocumentProps,
  DocumentState
> {
  constructor(props: Readonly<DocumentProps>) {
    super(props);
    this.state = {
      sel: undefined,
      fullText: undefined,
      fullTextNum: 0,
    };
  }

  componentDidMount() {
    this.componentDidUpdate(undefined, { sel: undefined });
  }

  componentDidUpdate(
    _prevProps: Readonly<DocumentProps> | undefined,
    prevState: Readonly<DocumentState> | EmptyDocumentState,
  ) {
    const { sel: prevSel } = prevState;
    const { sel, fullTextNum } = this.state;
    const {
      apiActions,
      doc: { mainId },
    } = this.props;
    if (sel !== prevSel && sel === 'fulltext') {
      const newFullTextNum = fullTextNum + 1;
      this.setState(
        {
          fullText: '[retrieving...]',
          fullTextNum: newFullTextNum,
        },
        () => {
          apiActions.getFulltext(mainId, (content, error) => {
            const { fullTextNum } = this.state;
            if (newFullTextNum === fullTextNum) {
              const err = error ? `\nERROR: ${error}` : '';
              this.setState({
                fullText: `${content ?? ''}${err}`,
              });
            }
          });
        },
      );
    }
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

  clickTab: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const target = e.currentTarget;
    const tab = target.getAttribute('data-tab') as Tab;
    if (!tab) {
      return;
    }
    this.setState({
      sel: tab,
    });
  };

  clickRecompute: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const {
      apiActions,
      doc: { mainId },
      collectionId,
      requestUpdate,
    } = this.props;
    if (collectionId < 0) {
      return;
    }
    apiActions.requeue(collectionId, [mainId], false, () => {
      requestUpdate();
    });
  };

  clickRefreshMeta: MouseEventHandler<HTMLSpanElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const {
      apiActions,
      doc: { mainId },
      collectionId,
      requestUpdate,
    } = this.props;
    if (collectionId < 0) {
      return;
    }
    apiActions.requeue(collectionId, [mainId], true, () => {
      requestUpdate();
    });
  };

  render() {
    const { doc, allScores, visIsRelative, isReadonly } = this.props;
    const {
      mainId,
      url,
      title,
      isValid,
      verifyReason,
      deepDiveReason,
      scores,
      error,
      tag,
      tagReason,
    } = doc;
    const { sel: maybeSel, fullText: content } = this.state;
    const sel = maybeSel ?? this.typeSelection(doc);
    return (
      <DocumentDiv>
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
            data-tab="tag"
            color={
              tagReason === undefined ? 'white' : tag ? '#ccebc5' : '#fed9a6'
            }
            active={tagReason !== undefined}
            selected={sel === 'tag'}
            onClick={tagReason !== undefined ? this.clickTab : undefined}>
            Tag: {tagReason === undefined ? '...' : tag ? `${tag}` : '???'}
          </DocumentTab>
          <DocumentTab
            data-main={mainId}
            data-tab="verify"
            color={
              isValid === undefined ? 'white' : isValid ? '#ccebc5' : '#fed9a6'
            }
            active={isValid !== undefined}
            selected={sel === 'verify'}
            onClick={isValid !== undefined ? this.clickTab : undefined}>
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
            data-tab="scores"
            color={deepDiveReason ? '#ccebc5' : 'white'}
            active={!!deepDiveReason}
            selected={sel === 'scores'}
            onClick={deepDiveReason ? this.clickTab : undefined}>
            Scores
          </DocumentTab>
          <DocumentTab
            data-tab="fulltext"
            color="white"
            active={true}
            selected={sel === 'fulltext'}
            onClick={this.clickTab}>
            Full-Text
          </DocumentTab>
          {error ? (
            <DocumentTab
              data-tab="error"
              color="#fbb4ae"
              active={true}
              selected={sel === 'error'}
              onClick={this.clickTab}>
              Error
            </DocumentTab>
          ) : null}
          <TabSpace />
          {!isReadonly ? (
            <React.Fragment>
              <DocumentTabButton
                data-main={mainId}
                onClick={this.clickRefreshMeta}>
                Refresh Metadata
              </DocumentTabButton>
              <DocumentTabButton
                data-main={mainId}
                onClick={this.clickRecompute}>
                Recompute
              </DocumentTabButton>
            </React.Fragment>
          ) : null}
        </DocumentTabList>
        {sel === 'tag' ? (
          <DocumentBody>
            <Output>{tagReason}</Output>
          </DocumentBody>
        ) : null}
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
            {deepDiveReason ? <Output>{deepDiveReason}</Output> : null}
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
      </DocumentDiv>
    );
  }
} // Document
