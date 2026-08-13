import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useObserverAssistantContext } from "./useObserverAssistantContext";

const mocks = vi.hoisted(() => ({
  registerPageContext: vi.fn(),
  clearPageContext: vi.fn(),
}));

vi.mock("@/lib/assistant/pageContext", () => ({
  usePageAssistantContext: () => ({
    registerPageContext: mocks.registerPageContext,
    clearPageContext: mocks.clearPageContext,
  }),
}));

describe("useObserverAssistantContext", () => {
  it("Observer 조회 scope만 Assistant page context에 등록한다", () => {
    const scope = {
      eqpId: "EQP-1",
      from: "2026-08-01",
      to: "2026-08-03",
      logTypes: ["eqp"],
      tipGroups: ["__ALL__"],
    };

    renderHook(() => useObserverAssistantContext(scope));
    const pageContext = mocks.registerPageContext.mock.calls.at(-1)[0];

    expect(pageContext).toEqual(
      expect.objectContaining({
        kind: "observer",
        label: "Observer · EQP-1",
        scope,
      }),
    );
    expect(pageContext.sendMessage).toBeUndefined();
  });
});
