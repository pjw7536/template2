import React, { Suspense, lazy } from "react";
import { TimelineShell } from "./components/TimelineShell";
import { PageLoader } from "./components/Loaders";

const TimelinePage = lazy(() => import("./pages/TimelinePage"));

const TimelineRoute = () => (
  <Suspense fallback={<PageLoader label="타임라인을 불러오는 중입니다" />}>
    <TimelinePage />
  </Suspense>
);

export const timelineRoutes = [
  {
    path: "timeline",
    element: <TimelineShell />,
    children: [
      { index: true, element: <TimelineRoute /> },
      { path: ":eqpId", element: <TimelineRoute /> },
    ],
  },
];
