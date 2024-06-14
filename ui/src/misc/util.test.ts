import {
  assertEqual,
  assertFail,
  assertNotEqual,
  assertTrue,
  range,
  SafeMap,
  SafeSet,
  toJson,
  union,
} from './util';

type ABObj = { a?: string; b: number };

test('SafeSet tests', () => {
  const set = new SafeSet<ABObj>();
  expect(set.size).toEqual(0);
  set.add({ a: 'a', b: 0 });
  expect(set.size).toEqual(1);
  expect(set.has({ a: 'a', b: 0 })).toBe(true);
  expect(set.has({ b: 0, a: 'a' })).toBe(true);
  expect(set.has({ a: undefined, b: 0 })).toBe(false);
  set.add({ a: undefined, b: 1 });
  expect(set.has({ a: 'a', b: 0 })).toBe(true);
  expect(set.has({ b: 1 })).toBe(true);
  expect(set.has({ a: undefined, b: 1 })).toBe(true);
  expect(set.has({ b: 1, a: undefined })).toBe(true);
  expect(set.has({ b: 0 })).toBe(false);
  set.add({ a: 'c', b: 2 });
  set.add({ b: 2, a: 'c' });
  set.add({ a: 'd', b: 3 });
  set.add({ b: 4 });
  set.delete({ b: 1 });
  expect(set.has({ a: 'a', b: 0 })).toBe(true);
  expect(set.has({ b: 1 })).toBe(false);
  expect(set.has({ a: 'c', b: 2 })).toBe(true);
  expect(set.has({ b: 3, a: 'd' })).toBe(true);
  expect(set.has({ b: 4 })).toBe(true);
  expect(set.has({ a: undefined, b: 4 })).toBe(true);
  set.delete({ b: 2, a: 'c' });
  expect(set.has({ a: 'c', b: 2 })).toBe(false);
  expect(set.has({ b: 2, a: 'c' })).toBe(false);
  expect(set.size).toBe(3);
  set.add({ b: 2, a: 'c' });
  expect(set.has({ a: 'c', b: 2 })).toBe(true);
  expect(set.has({ b: 2, a: 'c' })).toBe(true);
  expect(set.size).toBe(4);
  const ref = new Set([0, 2, 3, 4]);
  expect(new Set(Array.from(set.values()).map((el) => el.b))).toEqual(ref);
  let sCount = 0;
  set.forEach((value) => {
    expect(ref.has(value.b)).toBe(true);
    sCount += 1;
  });
  expect(sCount).toBe(4);
  const other = new SafeSet(set.values());
  set.clear();
  expect(set.size).toBe(0);
  expect(set.has({ a: 'a', b: 0 })).toBe(false);
  expect(set.has({ a: undefined, b: 1 })).toBe(false);
  expect(set.has({ a: 'c', b: 2 })).toBe(false);
  expect(set.has({ a: 'd', b: 3 })).toBe(false);
  expect(set.has({ a: undefined, b: 4 })).toBe(false);
  expect(other.size).toBe(4);
  expect(other.has({ a: 'a', b: 0 })).toBe(true);
  expect(other.has({ a: undefined, b: 1 })).toBe(false);
  expect(other.has({ a: 'c', b: 2 })).toBe(true);
  expect(other.has({ a: 'd', b: 3 })).toBe(true);
  expect(other.has({ a: undefined, b: 4 })).toBe(true);

  const map = new SafeMap(
    Array.from(other.values()).map((el) => [el.a, el.b]),
  );
  expect(map.size).toBe(4);
  let mCount = 0;
  map.forEach((value, key) => {
    expect(other.has({ b: value, a: key })).toBe(true);
    expect(ref.has(value)).toBe(true);
    mCount += 1;
  });
  expect(mCount).toBe(4);
  expect(new Set(Array.from(map.keys()))).toEqual(
    new Set([undefined, 'a', 'c', 'd']),
  );
  expect(Array.from(map.keys()).length).toBe(4);
  expect(new Set(Array.from(map.values()))).toEqual(ref);
  expect(Array.from(map.values()).length).toBe(4);
  const mSet = new SafeSet(
    Array.from(map.entries()).map((el) => ({ a: el[0], b: el[1] })),
  );
  expect(new Set(Array.from(mSet.values()))).toEqual(
    new Set(Array.from(other.values())),
  );
  map.clear();
  expect(map.size).toBe(0);
});

test('range tests', () => {
  expect(range(5)).toEqual([0, 1, 2, 3, 4]);
  expect(range(1)).toEqual([0]);
  expect(range(0)).toEqual([]);
  expect(range(0, 5)).toEqual([0, 1, 2, 3, 4]);
  expect(range(3, 5)).toEqual([3, 4]);
  expect(range(3, 7)).toEqual([3, 4, 5, 6]);
  expect(range(3, 4)).toEqual([3]);
  expect(range(3, 3)).toEqual([]);
  expect(range(4, 3)).toEqual([]);
});

test('union tests', () => {
  const origA = new Map([
    [0, 0],
    [1, 2],
  ]);
  const origB = new Map([
    [2, 2],
    [3, 4],
  ]);
  const origC = new Map([
    [1, 3],
    [2, 4],
  ]);
  const resAB = new Map([
    [0, 0],
    [1, 2],
    [2, 2],
    [3, 4],
  ]);
  const resAC = new Map([
    [0, 0],
    [1, 3],
    [2, 4],
  ]);
  const resCA = new Map([
    [0, 0],
    [1, 2],
    [2, 4],
  ]);
  const resBC = new Map([
    [1, 3],
    [2, 4],
    [3, 4],
  ]);
  const resCB = new Map([
    [1, 3],
    [2, 2],
    [3, 4],
  ]);
  const resABC = new Map([
    [0, 0],
    [1, 3],
    [2, 4],
    [3, 4],
  ]);
  const a = new Map(origA);
  const b = new Map(origB);
  const c = new Map(origC);
  expect(union(a, b)).toEqual(resAB);
  expect(a).toEqual(origA);
  expect(b).toEqual(origB);
  expect(union(a, c)).toEqual(resAC);
  expect(a).toEqual(origA);
  expect(c).toEqual(origC);
  expect(union(c, a)).toEqual(resCA);
  expect(c).toEqual(origC);
  expect(a).toEqual(origA);
  expect(union(b, c)).toEqual(resBC);
  expect(union(c, b)).toEqual(resCB);
  expect(union(union(a, b), c)).toEqual(resABC);
  expect(a).toEqual(origA);
  expect(b).toEqual(origB);
  expect(c).toEqual(origC);
});

test('assert tests', () => {
  const at = () => {
    assertTrue(false, 'expected throw');
  };
  expect(at).toThrow(Error);
  const ae = () => {
    assertEqual(3, 5, 'expected throw');
  };
  expect(ae).toThrow(Error);
  const an = () => {
    assertNotEqual(2, 2, 'expected throw');
  };
  expect(an).toThrow(Error);
  const err = () => {
    assertFail('test');
  };
  expect(err).toThrow(Error);
});

test('test json set', () => {
  expect(toJson({ a: new Set([1]) })).toEqual('{"a":[1]}');
});
