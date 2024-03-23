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

/** @type {{ [key: string]: number }} */
const renderCounts = {};

export function setLoading(
  /** @type {Element} */ element,
  /** @type {boolean} */ value,
  /** @type {boolean} */ force,
) {
  const eId = element.id;
  if (value) {
    renderCounts[eId] = (renderCounts[eId] ?? 0) + 1;
    // NOTE: only show loading if an action takes longer than 200ms
    setTimeout(() => {
      if (force || renderCounts[eId] > 0) {
        element.classList.add('loading');
      }
    }, 200);
  } else {
    renderCounts[eId] = Math.max((renderCounts[eId] ?? 0) - 1, 0);
    // NOTE: never show loading shorter than 200ms which causes blinking
    setTimeout(() => {
      if (force || renderCounts[eId] <= 0) {
        element.classList.remove('loading');
        renderCounts[eId] = 0;
      }
    }, 200);
  }
}
