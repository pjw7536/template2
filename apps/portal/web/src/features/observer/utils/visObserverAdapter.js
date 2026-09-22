import { DataSet } from "vis-data";

export async function loadVisObserverConstructor() {
  const { Timeline: Observer } = await import("vis-timeline/standalone");
  return Observer;
}

export function createVisObserver({
  Observer,
  container,
  items,
  groups,
  options,
}) {
  const dataset = new DataSet(items ?? []);
  const observer = new Observer(container, dataset, groups, options);

  return { observer, dataset };
}

export function replaceObserverItems(observer, dataset, items) {
  if (!observer || !dataset) return;

  const nextItems = items ?? [];
  const nextIds = new Set(nextItems.map((item) => item.id));
  const removedIds = dataset
    .getIds()
    .filter((itemId) => !nextIds.has(itemId));

  if (removedIds.length > 0) {
    dataset.remove(removedIds);
  }
  if (nextItems.length > 0) {
    dataset.update(nextItems);
  }
}

export function setObserverGroups(observer, groups) {
  if (!observer || !groups) return;

  const updatedGroups = groups.map((group) => ({
    ...group,
    visible: group.visible !== false,
  }));
  observer.setGroups(updatedGroups);
}

export function redrawObserverWithRange(observer, range) {
  if (!observer) return;

  observer.redraw();
  if (range) {
    observer.setWindow(range.start, range.end, { animation: false });
  }
}

export function applyObserverSelection(observer, selectedRow) {
  if (!observer) return null;

  if (selectedRow && observer.itemsData.get(selectedRow)) {
    const currentWindow = observer.getWindow();
    observer.setSelection([selectedRow]);
    observer.setWindow(currentWindow.start, currentWindow.end, {
      animation: false,
    });
    return currentWindow;
  }

  observer.setSelection([]);
  return null;
}
