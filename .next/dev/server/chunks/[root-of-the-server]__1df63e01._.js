module.exports = [
"[externals]/next/dist/compiled/next-server/app-route-turbo.runtime.dev.js [external] (next/dist/compiled/next-server/app-route-turbo.runtime.dev.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/compiled/next-server/app-route-turbo.runtime.dev.js", () => require("next/dist/compiled/next-server/app-route-turbo.runtime.dev.js"));

module.exports = mod;
}),
"[externals]/next/dist/compiled/@opentelemetry/api [external] (next/dist/compiled/@opentelemetry/api, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/compiled/@opentelemetry/api", () => require("next/dist/compiled/@opentelemetry/api"));

module.exports = mod;
}),
"[externals]/next/dist/compiled/next-server/app-page-turbo.runtime.dev.js [external] (next/dist/compiled/next-server/app-page-turbo.runtime.dev.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/compiled/next-server/app-page-turbo.runtime.dev.js", () => require("next/dist/compiled/next-server/app-page-turbo.runtime.dev.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/work-unit-async-storage.external.js [external] (next/dist/server/app-render/work-unit-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/work-unit-async-storage.external.js", () => require("next/dist/server/app-render/work-unit-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/work-async-storage.external.js [external] (next/dist/server/app-render/work-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/work-async-storage.external.js", () => require("next/dist/server/app-render/work-async-storage.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/shared/lib/no-fallback-error.external.js [external] (next/dist/shared/lib/no-fallback-error.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/shared/lib/no-fallback-error.external.js", () => require("next/dist/shared/lib/no-fallback-error.external.js"));

module.exports = mod;
}),
"[externals]/next/dist/server/app-render/after-task-async-storage.external.js [external] (next/dist/server/app-render/after-task-async-storage.external.js, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("next/dist/server/app-render/after-task-async-storage.external.js", () => require("next/dist/server/app-render/after-task-async-storage.external.js"));

module.exports = mod;
}),
"[project]/tailwind/src/lib/db.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getPool",
    ()=>getPool,
    "runQuery",
    ()=>runQuery
]);
(()=>{
    const e = new Error("Cannot find module 'mysql2/promise'");
    e.code = 'MODULE_NOT_FOUND';
    throw e;
})();
;
let pool = null;
function getConfig() {
    const host = process.env.DB_HOST ?? "127.0.0.1";
    const port = Number.parseInt(process.env.DB_PORT ?? "3307", 10);
    const user = process.env.DB_USER ?? "drone_user";
    const password = process.env.DB_PASSWORD ?? "dronepwd";
    const database = process.env.DB_NAME ?? "drone_sop";
    return {
        host,
        port: Number.isNaN(port) ? 3307 : port,
        user,
        password,
        database
    };
}
function getPool() {
    if (!pool) {
        const config = getConfig();
        pool = mysql.createPool({
            ...config,
            waitForConnections: true,
            connectionLimit: 10,
            timezone: "Z"
        });
    }
    return pool;
}
async function runQuery(sql, params = []) {
    const currentPool = getPool();
    const [rows] = await currentPool.query(sql, params);
    return rows;
}
}),
"[project]/tailwind/src/features/line-dashboard/api/get-line-dashboard.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getLineDashboard",
    ()=>getLineDashboard
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/db.js [app-route] (ecmascript)");
;
const DEFAULT_TABLE_NAME = "drone_sop_v3";
const TREND_LOOKBACK_DAYS = 90;
const RECENT_LIMIT = 10;
const toISODate = (input)=>{
    if (!input) return null;
    const date = input instanceof Date ? input : new Date(input);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
};
const mapSummaryRow = (row)=>({
        totalCount: Number(row.totalCount ?? 0),
        activeCount: Number(row.activeCount ?? 0),
        completedCount: Number(row.completedCount ?? 0),
        pendingJiraCount: Number(row.pendingJiraCount ?? 0),
        lotCount: Number(row.lotCount ?? 0),
        latestUpdatedAt: toISODate(row.latestUpdatedAt)
    });
const mapTrendRows = (rows)=>rows.map((row)=>({
            date: toISODate(row.day)?.slice(0, 10) ?? "",
            activeCount: Number(row.activeCount ?? 0),
            completedCount: Number(row.completedCount ?? 0)
        }));
const mapRecentRows = (rows)=>rows.map((row)=>({
            id: row.id,
            lotId: row.lot_id ?? null,
            status: row.status ?? null,
            createdAt: toISODate(row.created_at) ?? ""
        }));
async function getLineDashboard(lineId) {
    const [summaryRow] = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
      SELECT
        COUNT(*) AS totalCount,
        SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completedCount,
        SUM(CASE WHEN status <> 'Completed' THEN 1 ELSE 0 END) AS activeCount,
        SUM(CASE WHEN send_jira = 0 AND needtosend = 1 THEN 1 ELSE 0 END) AS pendingJiraCount,
        COUNT(DISTINCT lot_id) AS lotCount,
        MAX(updated_at) AS latestUpdatedAt
      FROM ${DEFAULT_TABLE_NAME}
      WHERE line_id = ?
    `, [
        lineId
    ]);
    if (!summaryRow || Number(summaryRow.totalCount ?? 0) === 0) {
        return null;
    }
    const trendRows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
      SELECT
        DATE(created_at) AS day,
        SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completedCount,
        SUM(CASE WHEN status <> 'Completed' THEN 1 ELSE 0 END) AS activeCount
      FROM ${DEFAULT_TABLE_NAME}
      WHERE line_id = ? AND created_at IS NOT NULL
        AND created_at >= DATE_SUB(CURDATE(), INTERVAL ? DAY)
      GROUP BY DATE(created_at)
      ORDER BY day ASC
    `, [
        lineId,
        TREND_LOOKBACK_DAYS
    ]);
    const recentRows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
      SELECT
        id,
        lot_id,
        status,
        created_at
      FROM ${DEFAULT_TABLE_NAME}
      WHERE line_id = ?
      ORDER BY created_at DESC
      LIMIT ?
    `, [
        lineId,
        RECENT_LIMIT
    ]);
    return {
        lineId,
        summary: mapSummaryRow(summaryRow),
        trend: mapTrendRows(trendRows),
        recent: mapRecentRows(recentRows)
    };
}
}),
"[project]/tailwind/src/features/line-dashboard/api/get-line-ids.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getDistinctLineIds",
    ()=>getDistinctLineIds
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/db.js [app-route] (ecmascript)");
;
const DEFAULT_TABLE_NAME = "drone_sop_v3";
async function getDistinctLineIds() {
    const rows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
      SELECT DISTINCT line_id
      FROM ${DEFAULT_TABLE_NAME}
      WHERE line_id IS NOT NULL AND line_id <> ''
      ORDER BY line_id
    `);
    return rows.map((row)=>row.line_id).filter((lineId)=>typeof lineId === "string" && lineId.length > 0);
}
}),
"[project]/tailwind/src/features/line-dashboard/api/index.js [app-route] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$get$2d$line$2d$dashboard$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/get-line-dashboard.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$get$2d$line$2d$ids$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/get-line-ids.js [app-route] (ecmascript)");
;
;
}),
"[project]/tailwind/src/features/line-dashboard/components/data-table/data-table.jsx [app-route] (client reference proxy) <module evaluation>", ((__turbopack_context__) => {
"use strict";

// This file is generated by next-core EcmascriptClientReferenceModule.
__turbopack_context__.s([
    "DataTable",
    ()=>DataTable
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-server-dom-turbopack-server.js [app-route] (ecmascript)");
;
const DataTable = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["registerClientReference"])(function() {
    throw new Error("Attempted to call DataTable() from the server but DataTable is on the client. It's not possible to invoke a client function from the server, it can only be rendered as a Component or passed to props of a Client Component.");
}, "[project]/tailwind/src/features/line-dashboard/components/data-table/data-table.jsx <module evaluation>", "DataTable");
}),
"[project]/tailwind/src/features/line-dashboard/components/data-table/data-table.jsx [app-route] (client reference proxy)", ((__turbopack_context__) => {
"use strict";

// This file is generated by next-core EcmascriptClientReferenceModule.
__turbopack_context__.s([
    "DataTable",
    ()=>DataTable
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-server-dom-turbopack-server.js [app-route] (ecmascript)");
;
const DataTable = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["registerClientReference"])(function() {
    throw new Error("Attempted to call DataTable() from the server but DataTable is on the client. It's not possible to invoke a client function from the server, it can only be rendered as a Component or passed to props of a Client Component.");
}, "[project]/tailwind/src/features/line-dashboard/components/data-table/data-table.jsx", "DataTable");
}),
"[project]/tailwind/src/features/line-dashboard/components/data-table/data-table.jsx [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$data$2d$table$2e$jsx__$5b$app$2d$route$5d$__$28$client__reference__proxy$29$__$3c$module__evaluation$3e$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/data-table/data-table.jsx [app-route] (client reference proxy) <module evaluation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$data$2d$table$2e$jsx__$5b$app$2d$route$5d$__$28$client__reference__proxy$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/data-table/data-table.jsx [app-route] (client reference proxy)");
;
__turbopack_context__.n(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$data$2d$table$2e$jsx__$5b$app$2d$route$5d$__$28$client__reference__proxy$29$__);
}),
"[project]/tailwind/src/features/line-dashboard/components/data-table/index.js [app-route] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$data$2d$table$2e$jsx__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/data-table/data-table.jsx [app-route] (ecmascript)");
;
}),
"[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LineSummaryCards",
    ()=>LineSummaryCards
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-dev-runtime.js [app-route] (ecmascript)");
(()=>{
    const e = new Error("Cannot find module '@tabler/icons-react'");
    e.code = 'MODULE_NOT_FOUND';
    throw e;
})();
(()=>{
    const e = new Error("Cannot find module '@/components/ui/card'");
    e.code = 'MODULE_NOT_FOUND';
    throw e;
})();
;
;
;
const numberFormatter = new Intl.NumberFormat("en-US");
const formatDelta = (delta)=>{
    if (delta === 0) return "0";
    return delta > 0 ? `+${numberFormatter.format(delta)}` : numberFormatter.format(delta);
};
function LineSummaryCards({ lineId, summary, trend }) {
    const sortedTrend = [
        ...trend
    ].sort((a, b)=>a.date.localeCompare(b.date));
    const latestPoint = sortedTrend.at(-1);
    const previousPoint = sortedTrend.at(-2);
    const activeDelta = latestPoint && previousPoint ? latestPoint.activeCount - previousPoint.activeCount : 0;
    const completedDelta = latestPoint && previousPoint ? latestPoint.completedCount - previousPoint.completedCount : 0;
    const completionRate = summary.totalCount > 0 ? Math.round(summary.completedCount / summary.totalCount * 100) : 0;
    const jiraSentCount = Math.max(summary.completedCount - summary.pendingJiraCount, 0);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "grid grid-cols-1 gap-4 px-4 md:grid-cols-3 lg:px-6",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(Card, {
                className: "h-full bg-gradient-to-t from-primary/5 to-card shadow-xs dark:bg-card",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardHeader, {
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardDescription, {
                                children: [
                                    "Total Records · ",
                                    lineId
                                ]
                            }, void 0, true, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 48,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardTitle, {
                                className: "text-3xl font-semibold tabular-nums",
                                children: numberFormatter.format(summary.totalCount)
                            }, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 49,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardAction, {}, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 52,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                        lineNumber: 47,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardFooter, {
                        className: "flex-col items-start gap-1 text-sm text-muted-foreground",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-center gap-2 font-medium text-foreground",
                                children: [
                                    "Current active items: ",
                                    numberFormatter.format(latestPoint?.activeCount ?? summary.activeCount)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 56,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                children: "Tracks total SOP records captured for the selected line."
                            }, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 59,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                        lineNumber: 55,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                lineNumber: 46,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(Card, {
                className: "h-full bg-gradient-to-t from-primary/5 to-card shadow-xs dark:bg-card",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardHeader, {
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardDescription, {
                                children: "Lots Completed"
                            }, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 65,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardTitle, {
                                className: "text-3xl font-semibold tabular-nums",
                                children: numberFormatter.format(summary.completedCount)
                            }, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 66,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardAction, {}, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 69,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                        lineNumber: 64,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardFooter, {
                        className: "flex-col items-start gap-1 text-sm text-muted-foreground",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-center gap-2 font-medium text-foreground",
                                children: [
                                    "Change vs last day ",
                                    formatDelta(completedDelta)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 73,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                children: [
                                    numberFormatter.format(summary.lotCount),
                                    " distinct lots processed overall."
                                ]
                            }, void 0, true, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 76,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                        lineNumber: 72,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                lineNumber: 63,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(Card, {
                className: "h-full bg-gradient-to-t from-primary/5 to-card shadow-xs dark:bg-card",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardHeader, {
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardDescription, {
                                children: "Pending Jira Dispatch"
                            }, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 82,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardTitle, {
                                className: "text-3xl font-semibold tabular-nums",
                                children: numberFormatter.format(summary.pendingJiraCount)
                            }, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 83,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardAction, {}, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 86,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                        lineNumber: 81,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])(CardFooter, {
                        className: "flex-col items-start gap-1 text-sm text-muted-foreground",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "flex items-center gap-2 font-medium text-foreground",
                                children: [
                                    "Jira sent: ",
                                    numberFormatter.format(jiraSentCount)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 91,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                children: "Open items where Jira has not been dispatched yet."
                            }, void 0, false, {
                                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                                lineNumber: 94,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                        lineNumber: 90,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
                lineNumber: 80,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx",
        lineNumber: 45,
        columnNumber: 5
    }, this);
}
}),
"[project]/tailwind/src/features/line-dashboard/components/line-activity-chart.jsx [app-route] (client reference proxy) <module evaluation>", ((__turbopack_context__) => {
"use strict";

// This file is generated by next-core EcmascriptClientReferenceModule.
__turbopack_context__.s([
    "LineActivityChart",
    ()=>LineActivityChart
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-server-dom-turbopack-server.js [app-route] (ecmascript)");
;
const LineActivityChart = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["registerClientReference"])(function() {
    throw new Error("Attempted to call LineActivityChart() from the server but LineActivityChart is on the client. It's not possible to invoke a client function from the server, it can only be rendered as a Component or passed to props of a Client Component.");
}, "[project]/tailwind/src/features/line-dashboard/components/line-activity-chart.jsx <module evaluation>", "LineActivityChart");
}),
"[project]/tailwind/src/features/line-dashboard/components/line-activity-chart.jsx [app-route] (client reference proxy)", ((__turbopack_context__) => {
"use strict";

// This file is generated by next-core EcmascriptClientReferenceModule.
__turbopack_context__.s([
    "LineActivityChart",
    ()=>LineActivityChart
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-server-dom-turbopack-server.js [app-route] (ecmascript)");
;
const LineActivityChart = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["registerClientReference"])(function() {
    throw new Error("Attempted to call LineActivityChart() from the server but LineActivityChart is on the client. It's not possible to invoke a client function from the server, it can only be rendered as a Component or passed to props of a Client Component.");
}, "[project]/tailwind/src/features/line-dashboard/components/line-activity-chart.jsx", "LineActivityChart");
}),
"[project]/tailwind/src/features/line-dashboard/components/line-activity-chart.jsx [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$line$2d$activity$2d$chart$2e$jsx__$5b$app$2d$route$5d$__$28$client__reference__proxy$29$__$3c$module__evaluation$3e$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/line-activity-chart.jsx [app-route] (client reference proxy) <module evaluation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$line$2d$activity$2d$chart$2e$jsx__$5b$app$2d$route$5d$__$28$client__reference__proxy$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/line-activity-chart.jsx [app-route] (client reference proxy)");
;
__turbopack_context__.n(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$line$2d$activity$2d$chart$2e$jsx__$5b$app$2d$route$5d$__$28$client__reference__proxy$29$__);
}),
"[project]/tailwind/src/features/line-dashboard/components/index.js [app-route] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/data-table/index.js [app-route] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$line$2d$summary$2d$cards$2e$jsx__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/line-summary-cards.jsx [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$line$2d$activity$2d$chart$2e$jsx__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/line-activity-chart.jsx [app-route] (ecmascript)");
;
;
;
}),
"[project]/tailwind/src/features/line-dashboard/index.js [app-route] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/index.js [app-route] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/index.js [app-route] (ecmascript) <locals>");
;
;
}),
"[project]/tailwind/src/features/line-dashboard/api/index.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getDistinctLineIds",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$get$2d$line$2d$ids$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getDistinctLineIds"],
    "getLineDashboard",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$get$2d$line$2d$dashboard$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getLineDashboard"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/index.js [app-route] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$get$2d$line$2d$dashboard$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/get-line-dashboard.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$get$2d$line$2d$ids$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/get-line-ids.js [app-route] (ecmascript)");
}),
"[project]/tailwind/src/app/api/lines/route.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "GET",
    ()=>GET,
    "dynamic",
    ()=>dynamic
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/server.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/index.js [app-route] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/index.js [app-route] (ecmascript)");
;
;
const dynamic = "force-dynamic";
async function GET() {
    try {
        const lineIds = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getDistinctLineIds"])();
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            lineIds
        });
    } catch (error) {
        console.error("Failed to fetch line IDs", error);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "Failed to load line identifiers"
        }, {
            status: 500
        });
    }
}
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__1df63e01._.js.map