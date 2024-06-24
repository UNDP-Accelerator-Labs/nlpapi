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
import styled from 'styled-components';
import { StatNumbers } from '../api/types';

const MAX_STAT_VALUE = 4;

const ORDER = [
  'cultural',
  'educational',
  'economic',
  'technological',
  'institutional',
  'legal',
  'political',
];

const cmpStatsFn = (a: string, b: string): number => {
  const aIx = ORDER.indexOf(a);
  const bIx = ORDER.indexOf(b);
  return aIx < 0 || bIx < 0 ? a.localeCompare(b) : aIx - bIx;
};

const SvgText = styled.text`
  font: 10px sans-serif;
  text-anchor: middle;
  dominant-baseline: hanging;
`;

type SpiderGraphProps = {
  stats: StatNumbers;
  cmpStats?: StatNumbers;
  radius?: number;
  padding?: number;
  color?: string;
  cmpColor?: string;
  isRelative: boolean;
  showCmpCircles?: boolean;
};

export default class SpiderGraph extends PureComponent<SpiderGraphProps> {
  getDenom(): number {
    const { stats, cmpStats, isRelative } = this.props;
    if (!isRelative) {
      return MAX_STAT_VALUE;
    }

    const getMax = (vals: StatNumbers): number =>
      Object.keys(vals).reduce((p, key) => Math.max(p, +(vals[key] ?? 0)), 0);

    return Math.max(getMax(stats), cmpStats ? getMax(cmpStats) : 0);
  }

  getRads(stats: StatNumbers, order: string[], radius: number): number[] {
    const allMax = this.getDenom();
    if (allMax === 0) {
      return order.map(() => 0);
    }
    return order.map((key) => (+(stats[key] ?? 0) / allMax) * radius);
  }

  getOutline(order: string[], angles: number[], rads: number[]): string {
    const coords = order.map((_, ix) => {
      const x = Math.cos((angles[ix] * Math.PI) / 180) * rads[ix];
      const y = Math.sin((angles[ix] * Math.PI) / 180) * rads[ix];
      return `${ix > 0 ? 'L' : 'M'}${x} ${y}`;
    });
    return `${(coords.length ? coords : ['M0 0']).join(' ')} Z`;
  }

  render() {
    const {
      radius = 100,
      padding = 5,
      color = 'black',
      cmpColor = '#f781bf',
      stats,
      cmpStats,
      showCmpCircles = false,
    } = this.props;
    const mid = radius + padding;
    const size = mid * 2;
    const order = Object.keys(stats).toSorted(cmpStatsFn);
    const count = Math.max(order.length, 1);
    const angles = order.map((_, ix) => (ix * 360) / count);
    const rads = this.getRads(stats, order, radius);
    const d = this.getOutline(order, angles, rads);
    const cmpRads = cmpStats ? this.getRads(cmpStats, order, radius) : [];
    const cmpD = cmpStats
      ? this.getOutline(order, angles, cmpRads)
      : undefined;
    const isShowCmpCircles = showCmpCircles && cmpRads.some((r) => r > 0);
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width={`${size}px`}
        height={`${size}px`}
        viewBox={`0 0 ${size} ${size}`}>
        <rect
          x={0}
          y={0}
          width={size}
          height={size}
          fill="white"
        />
        <g transform={`translate(${mid} ${mid})`}>
          {order.map((key, ix) => {
            const isLeft = angles[ix] > 90 && angles[ix] < 270;
            return (
              <g
                key={key}
                transform={`rotate(${angles[ix]})`}>
                <line
                  x1={0}
                  y1={0}
                  x2={radius}
                  y2={0}
                  stroke="darkgray"
                />
                <SvgText
                  x={0}
                  y={0}
                  transform={`translate(${radius * 0.5} ${
                    isLeft ? padding + 10 : padding
                  }) rotate(${isLeft ? 180 : 0})`}
                  fill="darkgray">
                  {key}
                </SvgText>
              </g>
            );
          })}
          {cmpD ? (
            <path
              d={cmpD}
              stroke={cmpColor}
              fill="none"
            />
          ) : null}
          {isShowCmpCircles
            ? order.map((key, ix) => (
                <g
                  key={key}
                  transform={`rotate(${angles[ix]})`}>
                  <circle
                    cx={cmpRads[ix]}
                    cy={0}
                    r={padding * 0.5}
                    fill={cmpColor}
                  />
                </g>
              ))
            : null}
          <path
            d={d}
            stroke={color}
            fill="none"
          />
          {order.map((key, ix) => (
            <g
              key={key}
              transform={`rotate(${angles[ix]})`}>
              <circle
                cx={rads[ix]}
                cy={0}
                r={padding * 0.5}
                fill={color}
              />
            </g>
          ))}
        </g>
      </svg>
    );
  }
} // SpiderGraph
