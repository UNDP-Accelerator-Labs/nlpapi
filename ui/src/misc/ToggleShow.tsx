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
import styled from 'styled-components';

const ToggleOuter = styled.div``;

const Toggle = styled.div`
  cursor: pointer;
  background-color: lightgray;

  &:hover {
    background-color: silver;
  }
`;

type ToggleShowProps = {
  toggle: string;
  children: React.ReactNode;
};

type ToggleShowState = {
  isOpen: boolean;
};

export default class ToggleShow extends PureComponent<
  ToggleShowProps,
  ToggleShowState
> {
  constructor(props: Readonly<ToggleShowProps>) {
    super(props);
    this.state = {
      isOpen: false,
    };
  }

  onClick: MouseEventHandler<HTMLDivElement> = (e) => {
    if (e.defaultPrevented) {
      return;
    }
    e.preventDefault();
    const { isOpen } = this.state;
    this.setState({ isOpen: !isOpen });
  };

  render() {
    const { children, toggle } = this.props;
    const { isOpen } = this.state;
    return (
      <ToggleOuter>
        <Toggle onClick={this.onClick}>{toggle}</Toggle>
        {isOpen ? children : null}
      </ToggleOuter>
    );
  }
}
