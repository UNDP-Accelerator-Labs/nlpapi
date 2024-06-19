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
  FormEventHandler,
  PureComponent,
} from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import ApiActions from '../api/ApiActions';
import { Collection, DeepDive } from '../api/types';
import { RootState } from '../store';
import { setCollection } from './CollectionStateSlice';

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

const Form = styled.form`
  display: flex;
  flex-direction: row;
  align-items: center;
`;

const InputText = styled.input`
  flex-shrink: 1;
  flex-grow: 1;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 14px;
  font-style: normal;
  font-variant: normal;
  font-weight: 400;
  line-height: 30px;
`;

const InputSubmit = styled.input`
  flex-shrink: 0;
  flex-grow: 0;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 14px;
  font-style: normal;
  font-variant: normal;
  font-weight: 400;
  line-height: 30px;
  height: 36px;
  cursor: pointer;
`;

interface CollectionsProps extends ConnectCollections {
  apiActions: ApiActions;
  canCreate: boolean;
  isCmp: boolean;
}

type CollectionsState = {
  collections: Collection[];
  needsUpdate: boolean;
  isCreating: boolean;
  apiNum: number;
};

class Collections extends PureComponent<CollectionsProps, CollectionsState> {
  constructor(props: Readonly<CollectionsProps>) {
    super(props);
    this.state = {
      collections: [],
      needsUpdate: true,
      isCreating: false,
      apiNum: 0,
    };
  }

  componentDidMount() {
    this.componentDidUpdate();
  }

  componentDidUpdate() {
    const { apiActions } = this.props;
    const { needsUpdate, apiNum } = this.state;
    if (needsUpdate) {
      const newApiNum = apiNum + 1;
      this.setState({ needsUpdate: false, apiNum: newApiNum }, () => {
        apiActions.collections((collections) => {
          const { apiNum } = this.state;
          if (apiNum !== newApiNum) {
            return;
          }
          this.setState({
            collections,
          });
        });
      });
    }
  }

  onChange: ChangeEventHandler<HTMLSelectElement> = (e) => {
    const { dispatch, isCmp } = this.props;
    const target = e.currentTarget;
    dispatch(setCollection({ collectionId: +target.value, isCmp }));
  };

  onCreate: FormEventHandler<HTMLFormElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { isCreating } = this.state;
    if (isCreating) {
      return;
    }
    const { dispatch, apiActions, isCmp } = this.props;
    const target = e.currentTarget;
    const formData = new FormData(target);
    const nameValue = formData.get('name');
    if (!nameValue) {
      return;
    }
    const newName = `${nameValue}`;
    if (!newName.length) {
      return;
    }
    const deepDive: DeepDive = 'circular_economy';
    this.setState(
      {
        isCreating: true,
      },
      () => {
        apiActions.addCollection(newName, deepDive, (collectionId) => {
          this.setState({
            needsUpdate: true,
            isCreating: false,
          });
          dispatch(setCollection({ collectionId, isCmp }));
        });
      },
    );
  };

  render() {
    const { collectionId, cmpCollectionId, canCreate, isCmp } = this.props;
    const { collections } = this.state;
    const cid = isCmp ? cmpCollectionId : collectionId;
    return (
      <React.Fragment>
        <Label>
          {isCmp ? 'Other ' : ''}Collection:{' '}
          <Select
            onChange={this.onChange}
            value={`${cid}`}>
            <Option value={`${-1}`}>
              {canCreate ? 'New Collection' : 'No Collection'}
            </Option>
            {collections.map(({ name, id }) => (
              <Option
                key={`${id}`}
                value={`${id}`}>
                {name}
              </Option>
            ))}
          </Select>
        </Label>
        {canCreate && cid < 0 ? (
          <Form onSubmit={this.onCreate}>
            <InputText
              type="text"
              name="name"
              autoComplete="off"
              placeholder="Collection Name"
            />
            <InputSubmit
              type="submit"
              value="Create"
            />
          </Form>
        ) : null}
      </React.Fragment>
    );
  }
} // Collections

const connector = connect((state: RootState) => ({
  collectionId: state.collectionState.collectionId,
  cmpCollectionId: state.collectionState.cmpCollectionId,
}));

export default connector(Collections);

type ConnectCollections = ConnectedProps<typeof connector>;
