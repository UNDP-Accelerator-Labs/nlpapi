/** @type {<T> (selector: string) => T} */
export function getElement(selector) {
  const res = document.querySelector(selector);
  if (!res) {
    throw new Error(`Could not find ${selector}`);
  }
  return res;
}
