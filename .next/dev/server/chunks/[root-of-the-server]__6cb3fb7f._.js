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
"[externals]/events [external] (events, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("events", () => require("events"));

module.exports = mod;
}),
"[externals]/process [external] (process, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("process", () => require("process"));

module.exports = mod;
}),
"[externals]/net [external] (net, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("net", () => require("net"));

module.exports = mod;
}),
"[externals]/tls [external] (tls, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("tls", () => require("tls"));

module.exports = mod;
}),
"[externals]/timers [external] (timers, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("timers", () => require("timers"));

module.exports = mod;
}),
"[externals]/stream [external] (stream, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("stream", () => require("stream"));

module.exports = mod;
}),
"[externals]/buffer [external] (buffer, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("buffer", () => require("buffer"));

module.exports = mod;
}),
"[externals]/string_decoder [external] (string_decoder, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("string_decoder", () => require("string_decoder"));

module.exports = mod;
}),
"[externals]/crypto [external] (crypto, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("crypto", () => require("crypto"));

module.exports = mod;
}),
"[externals]/zlib [external] (zlib, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("zlib", () => require("zlib"));

module.exports = mod;
}),
"[externals]/util [external] (util, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("util", () => require("util"));

module.exports = mod;
}),
"[externals]/url [external] (url, cjs)", ((__turbopack_context__, module, exports) => {

const mod = __turbopack_context__.x("url", () => require("url"));

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
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$mysql2$40$3$2e$15$2e$3$2f$node_modules$2f$mysql2$2f$promise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/mysql2@3.15.3/node_modules/mysql2/promise.js [app-route] (ecmascript)");
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
        pool = __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$mysql2$40$3$2e$15$2e$3$2f$node_modules$2f$mysql2$2f$promise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["default"].createPool({
            ...config,
            waitForConnections: true,
            connectionLimit: 10,
            // ✅ 한국시간 (UTC+9)
            timezone: "+09:00"
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
"[project]/tailwind/src/features/line-dashboard/utils/transform-response.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "mapRecentRows",
    ()=>mapRecentRows,
    "mapSummaryRow",
    ()=>mapSummaryRow,
    "mapTrendRows",
    ()=>mapTrendRows,
    "normalizeLineId",
    ()=>normalizeLineId,
    "toISODate",
    ()=>toISODate
]);
function toISODate(input) {
    if (!input) return null;
    const date = input instanceof Date ? input : new Date(String(input));
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
}
function normalizeLineId(raw) {
    if (raw == null) return null;
    const value = String(raw).trim();
    return value.length === 0 ? null : value;
}
function mapSummaryRow(row) {
    return {
        totalCount: Number(row.totalCount ?? 0),
        activeCount: Number(row.activeCount ?? 0),
        completedCount: Number(row.completedCount ?? 0),
        pendingJiraCount: Number(row.pendingJiraCount ?? 0),
        lotCount: Number(row.lotCount ?? 0),
        latestUpdatedAt: toISODate(row.latestUpdatedAt)
    };
}
function mapTrendRows(rows) {
    return rows.map((row)=>({
            date: (toISODate(row.day) ?? "").slice(0, 10),
            activeCount: Number(row.activeCount ?? 0),
            completedCount: Number(row.completedCount ?? 0)
        }));
}
function mapRecentRows(rows) {
    return rows.map((row)=>({
            id: row.id,
            lotId: row.lot_id ?? null,
            status: row.status ?? null,
            createdAt: toISODate(row.created_at) ?? ""
        }));
}
}),
"[project]/tailwind/src/features/line-dashboard/api/line-dashboard.api.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/features/line-dashboard/api/line-dashboard.api.js
__turbopack_context__.s([
    "getDistinctLineIds",
    ()=>getDistinctLineIds,
    "getLineDashboard",
    ()=>getLineDashboard
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/db.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$utils$2f$transform$2d$response$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/utils/transform-response.js [app-route] (ecmascript)");
;
;
/**
 * ---------------------------------------------------------------------------------------
 * 상수/환경
 * ---------------------------------------------------------------------------------------
 */ const DEFAULT_TABLE_NAME = "drone_sop_v3" // 기본 테이블명
;
const TREND_LOOKBACK_DAYS = 90 // 트렌드 조회 기간(일)
;
const RECENT_LIMIT = 10 // 최근 항목 개수
;
/**
 * ---------------------------------------------------------------------------------------
 * SQL 템플릿
 * 식별자는 상수로, 값은 전부 바인딩
 * ---------------------------------------------------------------------------------------
 */ const SQL = {
    summary: `
    SELECT
      COUNT(*) AS totalCount,
      SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completedCount,
      SUM(CASE WHEN status <> 'Completed' THEN 1 ELSE 0 END) AS activeCount,
      SUM(CASE WHEN send_jira = 0 AND needtosend = 1 THEN 1 ELSE 0 END) AS pendingJiraCount,
      COUNT(DISTINCT lot_id) AS lotCount,
      MAX(updated_at) AS latestUpdatedAt
    FROM ${DEFAULT_TABLE_NAME}
    WHERE line_id = ?
  `,
    trend: `
    SELECT
      DATE(created_at) AS day,
      SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completedCount,
      SUM(CASE WHEN status <> 'Completed' THEN 1 ELSE 0 END) AS activeCount
    FROM ${DEFAULT_TABLE_NAME}
    WHERE line_id = ?
      AND created_at IS NOT NULL
      AND created_at >= DATE_SUB(CURDATE(), INTERVAL ? DAY)
    GROUP BY DATE(created_at)
    ORDER BY day ASC
  `,
    recent: `
    SELECT
      id, lot_id, status, created_at
    FROM ${DEFAULT_TABLE_NAME}
    WHERE line_id = ?
    ORDER BY created_at DESC
    LIMIT ?
  `
};
async function getLineDashboard(lineIdRaw) {
    const lineId = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$utils$2f$transform$2d$response$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["normalizeLineId"])(lineIdRaw);
    if (!lineId) {
        throw new Error("lineId가 비어있습니다.");
    }
    // 1) 요약 데이터 조회
    const [summaryRow] = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(SQL.summary, [
        lineId
    ]);
    const total = Number(summaryRow?.totalCount ?? 0);
    if (!summaryRow || total === 0) {
        return null;
    }
    // 2) 트렌드 + 최근 목록 병렬 조회 (성능 향상)
    const [trendRows, recentRows] = await Promise.all([
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(SQL.trend, [
            lineId,
            TREND_LOOKBACK_DAYS
        ]),
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(SQL.recent, [
            lineId,
            RECENT_LIMIT
        ])
    ]);
    return {
        lineId,
        summary: (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$utils$2f$transform$2d$response$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["mapSummaryRow"])(summaryRow),
        trend: (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$utils$2f$transform$2d$response$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["mapTrendRows"])(trendRows),
        recent: (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$utils$2f$transform$2d$response$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["mapRecentRows"])(recentRows)
    };
}
const LINE_SDWT_TABLE_NAME = "line_sdwt";
async function getDistinctLineIds() {
    const rows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
      SELECT DISTINCT line_id
      FROM ${LINE_SDWT_TABLE_NAME}
      WHERE line_id IS NOT NULL AND line_id <> ''
      ORDER BY line_id
    `);
    return rows.map((row)=>row.line_id).filter((lineId)=>typeof lineId === "string" && lineId.length > 0);
}
}),
"[project]/tailwind/src/features/line-dashboard/api/index.js [app-route] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$line$2d$dashboard$2e$api$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/line-dashboard.api.js [app-route] (ecmascript)");
;
}),
"[project]/tailwind/src/app/api/line-dashboard/route.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "GET",
    ()=>GET
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/server.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/index.js [app-route] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$line$2d$dashboard$2e$api$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/line-dashboard.api.js [app-route] (ecmascript)");
;
;
async function GET(request) {
    const { searchParams } = new URL(request.url);
    const lineId = searchParams.get("lineId");
    if (!lineId) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "lineId is required"
        }, {
            status: 400
        });
    }
    try {
        const data = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$line$2d$dashboard$2e$api$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getLineDashboard"])(lineId);
        if (!data) {
            return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
                data: null
            }, {
                status: 404
            });
        }
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load line dashboard";
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: message
        }, {
            status: 500
        });
    }
}
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__6cb3fb7f._.js.map