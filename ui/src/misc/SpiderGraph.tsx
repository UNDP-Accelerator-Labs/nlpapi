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
import { StatFinal, StatFull } from '../api/types';

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
  stats: StatFull;
  cmpStats?: StatFull;
  radius?: number;
  padding?: number;
  color?: string;
  cmpColor?: string;
  isRelative: boolean;
  showCmpCircles?: boolean;
};

type EmptySpiderGraphProps = {
  stats: undefined;
  cmpStats: undefined;
};

type SpiderGraphState = {
  finalStats?: StatFinal;
  finalCmpStats?: StatFinal;
};

export default class SpiderGraph extends PureComponent<
  SpiderGraphProps,
  SpiderGraphState
> {
  constructor(props: Readonly<SpiderGraphProps>) {
    super(props);
    this.state = {
      finalStats: undefined,
      finalCmpStats: undefined,
    };
  }

  componentDidMount() {
    this.componentDidUpdate({
      stats: undefined,
      cmpStats: undefined,
    });
  }

  componentDidUpdate(
    prevProps: Readonly<SpiderGraphProps> | EmptySpiderGraphProps,
  ) {
    const { stats: prevStats, cmpStats: prevCmpStats } = prevProps;
    const { stats, cmpStats } = this.props;
    if (prevStats !== stats) {
      this.setState({
        finalStats: this.convertStats(stats),
      });
    }
    if (prevCmpStats !== cmpStats && cmpStats) {
      this.setState({
        finalCmpStats: this.convertStats(cmpStats),
      });
    }
  }

  convertStats(stats: StatFull): StatFinal {
    const ci = 0.95;
    const c = (1.0 - ci) * 0.5 + ci;
    return Object.fromEntries(
      Object.entries(stats).map(([key, { mean, stddev, count }]) => [
        key,
        {
          mean,
          ciMax: Math.min(
            MAX_STAT_VALUE,
            mean + (c * stddev) / Math.sqrt(count),
          ),
          ciMin: Math.max(0, mean - (c * stddev) / Math.sqrt(count)),
        },
      ]),
    );
  }

  getDenom(): number {
    const { isRelative } = this.props;
    if (!isRelative) {
      return MAX_STAT_VALUE;
    }
    const { finalStats, finalCmpStats } = this.state;

    const getMax = (vals: StatFinal): number =>
      Object.keys(vals).reduce(
        (p, key) => Math.max(p, +(vals[key].ciMax ?? 0)),
        0,
      );

    return Math.max(
      finalStats ? getMax(finalStats) : 0,
      finalCmpStats ? getMax(finalCmpStats) : 0,
    );
  }

  getRads(stats: StatFinal, order: string[], radius: number): number[] {
    const allMax = this.getDenom();
    if (allMax === 0) {
      return order.map(() => 0);
    }
    return order.map((key) => (+(stats[key].mean ?? 0) / allMax) * radius);
  }

  getRange(
    stats: StatFinal,
    order: string[],
    radius: number,
    isMax: boolean,
  ): number[] {
    const allMax = this.getDenom();
    if (allMax === 0) {
      return order.map(() => 0);
    }
    return order.map(
      (key) =>
        (+((isMax ? stats[key].ciMax : stats[key].ciMin) ?? 0) / allMax) *
        radius,
    );
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
      showCmpCircles = false,
    } = this.props;
    const { finalStats: finalStats = {}, finalCmpStats: finalCmpStats = {} } =
      this.state;
    const mid = radius + padding;
    const size = mid * 2;
    const order = Object.keys(finalStats).toSorted(cmpStatsFn);
    const count = Math.max(order.length, 1);
    const angles = order.map((_, ix) => (ix * 360) / count);

    const getMean = (stats: StatFinal): [number[], string] => {
      const rads = this.getRads(stats, order, radius);
      const d = this.getOutline(order, angles, rads);
      return [rads, d];
    };

    const getArea = (stats: StatFinal): string => {
      const maxR = this.getRange(stats, order, radius, true);
      const minR = this.getRange(stats, order, radius, false);
      const maxBound = this.getOutline(order, angles, maxR);
      const minBound = this.getOutline(order, angles, minR);
      return `${maxBound} ${minBound}`;
    };

    const [rads, d] = getMean(finalStats);
    const area = getArea(finalStats);
    const [cmpRads, cmpD] = finalCmpStats
      ? getMean(finalCmpStats)
      : [[], undefined];
    const cmpArea = finalCmpStats ? getArea(finalCmpStats) : undefined;
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
          {cmpArea ? (
            <path
              d={cmpArea}
              stroke="none"
              fill={cmpColor}
              fillRule="evenodd"
              opacity={0.2}
            />
          ) : null}
          <path
            d={area}
            stroke="none"
            fill={color}
            fillRule="evenodd"
            opacity={0.2}
          />
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
