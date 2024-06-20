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
import { ChangeEventHandler, PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import { DocumentObj, Filter } from '../api/types';
import { RootState } from '../store';
import { setCollectionTag } from './CollectionStateSlice';

const ALL_TAG = '_all';

type TagStat = {
  tag: string | null;
  name: string;
  totalCount: number;
  completeCount: number;
};

type TagStatDict = { [key: string]: TagStat };

const NO_TAGS: TagStat[] = [
  { tag: null, name: 'All', totalCount: 0, completeCount: 0 },
];

const Select = styled.select`
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 14px;
  font-style: normal;
  font-variant: normal;
  font-weight: 400;
  line-height: 30px;
`;

const Option = styled.option``;

interface TagFilterProps extends ConnectTagFilter {
  documents: DocumentObj[];
  isCmp: boolean;
  isType: (doc: DocumentObj, filter: Filter) => boolean;
}

type EmptyTagFilterProps = {
  documents: DocumentObj[];
};

type TagFilterState = {
  tags: TagStat[];
};

class TagFilter extends PureComponent<TagFilterProps, TagFilterState> {
  constructor(props: Readonly<TagFilterProps>) {
    super(props);
    this.state = {
      tags: NO_TAGS,
    };
  }

  componentDidMount() {
    this.componentDidUpdate({ documents: [] });
  }

  componentDidUpdate(
    prevProps: Readonly<TagFilterProps> | EmptyTagFilterProps,
  ) {
    const { documents: prevDocuments } = prevProps;
    const { documents } = this.props;
    if (documents !== prevDocuments) {
      this.setState({ tags: this.computeTags(documents) });
    }
  }

  onTagChange: ChangeEventHandler<HTMLSelectElement> = (e) => {
    const { dispatch, isCmp } = this.props;
    const target = e.currentTarget;
    const value = target.value;
    dispatch(
      setCollectionTag({
        collectionTag: value === ALL_TAG ? null : value,
        isCmp,
      }),
    );
  };

  computeTags(docs: DocumentObj[]): TagStat[] {
    if (!docs.length) {
      return NO_TAGS;
    }
    const { isType } = this.props;
    const tally: TagStatDict = {};

    const addDoc = (tag: string | undefined, doc: DocumentObj) => {
      const sane = tag ?? ALL_TAG;
      const isComplete = isType(doc, 'complete');
      const cur = tally[sane];
      if (!cur) {
        tally[sane] = {
          name: tag ?? 'All',
          tag: tag ?? null,
          totalCount: 1,
          completeCount: isComplete ? 1 : 0,
        };
      } else {
        cur.totalCount += 1;
        if (isComplete) {
          cur.completeCount += 1;
        }
      }
    };

    docs.forEach((doc) => {
      const { tag } = doc;
      addDoc(tag, doc);
      if (tag) {
        addDoc(undefined, doc);
      }
    });
    return Object.keys(tally)
      .map((key) => tally[key])
      .toSorted(
        ({ tag: ta, completeCount: ca }, { tag: tb, completeCount: cb }) =>
          (ca === 0) !== (cb === 0)
            ? cb - ca
            : ta
            ? tb
              ? ta.localeCompare(tb)
              : 1
            : -1,
      );
  }

  render() {
    const { isCmp, collectionTag, cmpCollectionTag } = this.props;
    const { tags } = this.state;
    const currentTag = isCmp ? cmpCollectionTag : collectionTag;
    return (
      <label>
        {isCmp ? 'Compare' : 'Filter'} Tag:{' '}
        <Select
          onChange={this.onTagChange}
          value={currentTag ?? ALL_TAG}>
          {tags.map(({ tag, name, totalCount, completeCount }) => (
            <Option
              key={tag ?? ALL_TAG}
              value={tag ?? ALL_TAG}>
              {name} {completeCount} / {totalCount}
            </Option>
          ))}
        </Select>
      </label>
    );
  }
} // TagFilter

const connector = connect((state: RootState) => ({
  collectionTag: state.collectionState.collectionTag,
  cmpCollectionTag: state.collectionState.cmpCollectionTag,
}));

export default connector(TagFilter);

type ConnectTagFilter = ConnectedProps<typeof connector>;
