// src/features/timeline/hooks/useVisTimeline.js (일부 수정)
import { useEffect, useRef } from "react";
import { DataSet } from "vis-data";
import { useTimelineSelectionStore } from "../store/useTimelineSelectionStore";
import { useTimelineStore } from "../store/timelineStore";

/**
 * vis-timeline 라이프사이클을 래핑하는 훅.
 * - 한 번 만든 Timeline/DataSet 인스턴스를 재사용
 * - 다른 타임라인들과 범위를 동기화
 * - 전역 선택 상태와 연결
 */
export function useVisTimeline({ containerRef, groups, items, options }) {
  const tlRef = useRef(null);
  const currentRangeRef = useRef(null);
  const previousHeightRef = useRef(null); // 이전 높이를 저장
  const datasetRef = useRef(null); // DataSet 인스턴스 재사용을 위한 ref

  const { setSelectedRow, selectedRow } = useTimelineSelectionStore();
  const { register, unregister, syncRange } = useTimelineStore();

  // 1. 컴포넌트 마운트 시 한 번만 인스턴스 생성
  useEffect(() => {
    let mounted = true;
    (async () => {
      const { Timeline } = await import("vis-timeline/standalone");
      if (!mounted || !containerRef.current) return;

      datasetRef.current = new DataSet(items);
      tlRef.current = new Timeline(
        containerRef.current,
        datasetRef.current,
        groups,
        options
      );

      register(tlRef.current);

      tlRef.current.on("rangechange", ({ start, end }) => {
        currentRangeRef.current = { start, end };
        syncRange(tlRef.current, start, end);
      });

      tlRef.current.on("select", ({ items }) => {
        const currentSelected =
          useTimelineSelectionStore.getState().selectedRow;
        if (items && items.length > 0) {
          if (String(currentSelected) === String(items[0])) {
            setSelectedRow(null, "timeline");
            tlRef.current.setSelection([]);
          } else {
            setSelectedRow(items[0], "timeline");
          }
        } else {
          setSelectedRow(null, "timeline");
        }
      });
    })();

    return () => {
      mounted = false;
      if (tlRef.current) {
        unregister(tlRef.current);
        tlRef.current.destroy();
      }
      datasetRef.current = null;
    };
  }, [register, unregister, syncRange, setSelectedRow]);

  // 2. 아이템 배열이 바뀌면 데이터셋 업데이트
  useEffect(() => {
    if (tlRef.current && datasetRef.current) {
      datasetRef.current.clear();
      datasetRef.current.add(items);
      tlRef.current.setItems(datasetRef.current);
    }
  }, [items]);

  // 3. 그룹 정보 변경 시 갱신
  useEffect(() => {
    if (tlRef.current && groups) {
      const updatedGroups = groups.map((g) => ({
        ...g,
        visible: g.visible !== false,
      }));
      tlRef.current.setGroups(updatedGroups);
    }
  }, [groups]);

  // 4. 옵션 변경 시 업데이트 (특히 높이)
  useEffect(() => {
    if (tlRef.current && options) {
      const heightChanged = previousHeightRef.current !== options.height;

      tlRef.current.setOptions(options);

      if (heightChanged) {
        previousHeightRef.current = options.height;

        setTimeout(() => {
          if (tlRef.current) {
            tlRef.current.redraw();
            if (currentRangeRef.current) {
              tlRef.current.setWindow(
                currentRangeRef.current.start,
                currentRangeRef.current.end,
                { animation: false }
              );
            }
          }
        }, 100);
      }
    }
  }, [options]);

  // 5. 외부에서 선택된 행을 타임라인에 반영
  useEffect(() => {
    if (tlRef.current) {
      if (selectedRow && tlRef.current.itemsData.get(selectedRow)) {
        const currentWindow = tlRef.current.getWindow();
        currentRangeRef.current = {
          start: currentWindow.start,
          end: currentWindow.end,
        };

        tlRef.current.setSelection([selectedRow]);

        if (currentRangeRef.current) {
          tlRef.current.setWindow(
            currentRangeRef.current.start,
            currentRangeRef.current.end,
            { animation: false }
          );
        }
      } else {
        tlRef.current.setSelection([]);
      }
    }
  }, [selectedRow]);

  return tlRef;
}
