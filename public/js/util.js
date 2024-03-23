// @ts-check

/** @type {<T extends Element> (selector: string) => T} */
export function getElement(selector) {
  const res = document.querySelector(selector);
  if (!res) {
    throw new Error(`Could not find ${selector}`);
  }
  // @ts-ignore Type 'Element' is not assignable to type 'T'.
  return res;
}

/** @type {{ [key: string]: boolean }} */
const isLoading = {};

export function setLoading(
  /** @type {Element} */ element,
  /** @type {boolean} */ value,
) {
  const eId = element.id;
  if (value) {
    isLoading[eId] = true;
    // NOTE: only show loading if an action takes longer than 200ms
    setTimeout(() => {
      if (isLoading[eId]) {
        element.classList.add('loading');
      }
    }, 200);
  } else {
    isLoading[eId] = false;
    // NOTE: never show loading shorter than 200ms which causes blinking
    setTimeout(() => {
      if (!isLoading[eId]) {
        element.classList.remove('loading');
      }
    }, 200);
  }
}
