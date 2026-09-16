import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LogDetailSection from "./LogDetailSection";

vi.mock("./CtttmDetail", () => ({
  default: ({ onStreamingProgress }) => (
    <button type="button" onClick={onStreamingProgress}>
      스트리밍 진행
    </button>
  ),
}));

function configureScrollContainer(element) {
  let scrollTop = 0;
  let scrollHeight = 500;
  const clientHeight = 100;

  Object.defineProperties(element, {
    clientHeight: {
      configurable: true,
      get: () => clientHeight,
    },
    scrollHeight: {
      configurable: true,
      get: () => scrollHeight,
    },
    scrollTop: {
      configurable: true,
      get: () => scrollTop,
      set: (value) => {
        scrollTop = Math.max(0, Math.min(value, scrollHeight - clientHeight));
      },
    },
  });

  return {
    getScrollTop: () => scrollTop,
    setScrollHeight: (value) => {
      scrollHeight = value;
    },
    setScrollTop: (value) => {
      scrollTop = value;
    },
  };
}

describe("LogDetailSection Summary 자동 스크롤", () => {
  beforeEach(() => {
    const getComputedStyle = window.getComputedStyle.bind(window);
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      callback();
      return 1;
    });
    vi.spyOn(window, "getComputedStyle").mockImplementation((element) => {
      const computedStyle = getComputedStyle(element);
      if (element.dataset.testid !== "scroll-container") return computedStyle;

      return new Proxy(computedStyle, {
        get(target, property) {
          if (property === "overflowY") return "auto";
          const value = Reflect.get(target, property, target);
          return typeof value === "function" ? value.bind(target) : value;
        },
      });
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("사용자가 위로 스크롤하면 자동 추적을 멈추고 하단에서 재개한다", () => {
    render(
      <div data-testid="scroll-container" className="overflow-y-auto">
        <LogDetailSection
          log={{ id: 1, logType: "CTTTM", eventTime: "2026-08-12T10:00:00" }}
          overflowClassName="overflow-visible"
        />
      </div>,
    );

    const scrollContainer = screen.getByTestId("scroll-container");
    const scrollState = configureScrollContainer(scrollContainer);
    const progressButton = screen.getByRole("button", { name: "스트리밍 진행" });

    fireEvent.click(progressButton);
    expect(scrollState.getScrollTop()).toBe(400);

    scrollState.setScrollTop(240);
    fireEvent.scroll(scrollContainer);
    scrollState.setScrollHeight(600);
    fireEvent.click(progressButton);
    expect(scrollState.getScrollTop()).toBe(240);

    scrollState.setScrollTop(500);
    fireEvent.scroll(scrollContainer);
    scrollState.setScrollHeight(700);
    fireEvent.click(progressButton);
    expect(scrollState.getScrollTop()).toBe(600);
  });
});
