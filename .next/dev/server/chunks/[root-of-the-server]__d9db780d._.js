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
"[project]/tailwind/src/features/line-dashboard/components/index.js [app-route] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/data-table/index.js [app-route] (ecmascript) <locals>");
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

//# sourceMappingURL=%5Broot-of-the-server%5D__d9db780d._.js.map