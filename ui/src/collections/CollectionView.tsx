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
import { PureComponent } from 'react';
import { ConnectedProps, connect } from 'react-redux';
import styled from 'styled-components';
import ApiActions from '../api/ApiActions';
import { DocumentObj } from '../api/types';
import ToggleShow from '../misc/ToggleShow';
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

const Documents = styled.div`
  flex-grow: 1;
  overflow: auto;
`;

const Document = styled.div`
  border: 1px silver solid;
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
};

class CollectionView extends PureComponent<
  CollectionViewProps,
  CollectionViewState
> {
  constructor(props: Readonly<CollectionViewProps>) {
    super(props);
    this.state = {
      documents: [],
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
      if (collectionId < 0) {
        this.setState({ documents: [] });
      } else {
        apiActions.documents(collectionId, (documents) => {
          const { collectionId: currentCollectionId } = this.props;
          if (collectionId === currentCollectionId) {
            this.setState({ documents });
          }
        });
      }
    }
  }

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
    const { documents } = this.state;
    const { total, included, excluded, complete, errors } =
      this.computeStats();
    return (
      <VMain>
        <Collections
          apiActions={apiActions}
          canCreate={true}
        />
        <div>
          <span>Total: {total}</span>
          <span> Included: {included}</span>
          <span> Excluded: {excluded}</span>
          <span> Complete: {complete}</span>
          <span> Errors: {errors}</span>
        </div>
        <Documents>
          {documents.map(({ mainId, isValid, verifyReason, error }) => {
            return (
              <Document>
                {mainId}
                <ToggleShow
                  toggle={
                    isValid === undefined
                      ? 'pending'
                      : isValid
                      ? 'ok'
                      : 'excluded'
                  }>
                  {verifyReason}
                </ToggleShow>
                {error ? (
                  <ToggleShow toggle="error">{error}</ToggleShow>
                ) : null}
              </Document>
            );
          })}
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
