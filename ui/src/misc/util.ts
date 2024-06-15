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
// FIXME might be useful later
// ts-unused-exports:disable-next-line
export function timeout(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function range(from: number, to?: number): number[] {
  if (to === undefined) {
    to = from;
    from = 0;
  }
  if (from > to) {
    return [];
  }
  return Array.from(Array(to - from).keys()).map((cur) => from + cur);
}

export function union<K, V>(left: Map<K, V>, right: Map<K, V>): Map<K, V> {
  return new Map(
    Array.from(left.entries()).concat(Array.from(right.entries())),
  );
}

export function toJson(obj: any): string {
  return JSON.stringify(obj, (_key, value) => {
    if (value instanceof Set) {
      value = Array.from(value.keys());
    }
    return value;
  });
}

export function assertFail(e: any): never {
  throw new Error(`should not have happened: ${e}`);
}

export function assertTrue(value: boolean, e: any): asserts value {
  if (!value) {
    throw new Error(`assertion was not true: ${e}`);
  }
}

export function assertEqual<T>(
  actual: unknown,
  expected: T,
  name: string,
): asserts actual is T {
  if (actual !== expected) {
    throw new Error(`${name}: actual:${actual} !== expected:${expected}`);
  }
}

export function assertNotEqual(
  actual: unknown,
  expected: unknown,
  name: string,
): void {
  if (actual === expected) {
    throw new Error(`${name}: actual:${actual} === expected:${expected}`);
  }
}

function stringify(obj: any, space: string): string {
  return JSON.stringify(
    obj,
    (_k, value) => {
      if (
        value instanceof Object &&
        !(value instanceof Array) &&
        !(value instanceof Date) &&
        !(value instanceof Function)
      ) {
        value = Object.fromEntries(
          Object.keys(value)
            .sort()
            .map((k) => [k, value[k]])
            .filter(([_k, val]) => val !== undefined),
        );
      }
      return value;
    },
    space,
  );
}

function safeStringify(obj: any): string {
  return stringify(obj, '');
}

export class SafeMap<K, V> {
  private readonly mapValues: Map<string, V>;
  private readonly mapKeys: Map<string, K>;

  constructor(
    entries?: Iterable<readonly [K, V]> | ArrayLike<readonly [K, V]>,
  ) {
    if (entries !== undefined) {
      const es: (readonly [K, V])[] = Array.from(entries);
      this.mapValues = new Map(es.map((e) => [this.key(e[0]), e[1]]));
      this.mapKeys = new Map(es.map((e) => [this.key(e[0]), e[0]]));
    } else {
      this.mapValues = new Map();
      this.mapKeys = new Map();
    }
  }

  private key(key: Readonly<K>): string {
    return safeStringify(key);
  }

  clear(): void {
    this.mapValues.clear();
    this.mapKeys.clear();
  }

  delete(key: Readonly<K>): boolean {
    const k = this.key(key);
    this.mapKeys.delete(k);
    return this.mapValues.delete(k);
  }

  forEach(
    callbackfn: (value: V, key: K, map: this) => void,
    thisArg?: any,
  ): void {
    this.mapValues.forEach((value, key) => {
      const k = this.mapKeys.get(key);
      if (k === undefined) {
        assertTrue(this.mapKeys.has(key), `${key} not in map`);
        const uk = k as K; // NOTE: hack to allow undefined in a key type
        callbackfn.call(thisArg, value, uk, this);
        return;
      }
      callbackfn.call(thisArg, value, k, this);
    }, this);
  }

  get(key: Readonly<K>): V | undefined {
    const k = this.key(key);
    return this.mapValues.get(k);
  }

  has(key: Readonly<K>): boolean {
    const k = this.key(key);
    return this.mapValues.has(k);
  }

  set(key: Readonly<K>, value: V): this {
    const k = this.key(key);
    this.mapKeys.set(k, key);
    this.mapValues.set(k, value);
    return this;
  }

  get size(): number {
    return this.mapValues.size;
  }

  keys(): IterableIterator<K> {
    return this.mapKeys.values();
  }

  values(): IterableIterator<V> {
    return this.mapValues.values();
  }

  entries(): IterableIterator<[K, V]> {
    const res: [K, V][] = Array.from(this.mapValues.entries()).map((entry) => {
      const [key, value] = entry;
      const k = this.mapKeys.get(key);
      if (k === undefined) {
        assertTrue(this.mapKeys.has(key), `${key} not in map`);
        const uk = k as K; // NOTE: hack to allow undefined in a key type
        return [uk, value];
      }
      return [k, value];
    });
    return res.values();
  }
} // SafeMap

export class SafeSet<V> {
  private readonly setValues: Map<string, V>;

  constructor(entries?: Iterable<V> | ArrayLike<V>) {
    if (entries !== undefined) {
      const es: V[] = Array.from(entries);
      this.setValues = new Map(es.map((e) => [this.key(e), e]));
    } else {
      this.setValues = new Map();
    }
  }

  private key(value: Readonly<V>): string {
    return safeStringify(value);
  }

  clear(): void {
    this.setValues.clear();
  }

  delete(value: Readonly<V>): boolean {
    const v = this.key(value);
    return this.setValues.delete(v);
  }

  forEach(
    callbackfn: (value: V, value2: V, set: this) => void,
    thisArg?: any,
  ): void {
    this.setValues.forEach((value) => {
      callbackfn.call(thisArg, value, value, this);
    }, this);
  }

  has(value: Readonly<V>): boolean {
    const v = this.key(value);
    return this.setValues.has(v);
  }

  add(value: V): this {
    const v = this.key(value);
    this.setValues.set(v, value);
    return this;
  }

  get size(): number {
    return this.setValues.size;
  }

  values(): IterableIterator<V> {
    return this.setValues.values();
  }
} // SafeSet
