import { create } from "zustand";

export const useTimelineStore = create((set, get) => ({
  /* —— Timeline 전용 상태 —— */
  showLegend: false,
  selectedTipGroups: ["__ALL__"],

  /* —— Timeline 상태 변경 액션 —— */
  setShowLegend: (show) => set({ showLegend: show }),
  toggleShowLegend: () => set((state) => ({ showLegend: !state.showLegend })),
  setSelectedTipGroups: (groups) => set({ selectedTipGroups: groups }),

  /* —— vis-timeline 인스턴스 풀 관리 —— */
  pool: [],
  register: (tl) => set((s) => ({ pool: [...s.pool, tl] })),
  unregister: (tl) => set((s) => ({ pool: s.pool.filter((t) => t !== tl) })),

  syncRange: (self, start, end) => {
    const { pool } = get();
    pool.forEach((tl) => {
      if (tl !== self) tl.setWindow(start, end, { animation: false });
    });
  },
}));
