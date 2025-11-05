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
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$mysql2$2f$promise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/mysql2/promise.js [app-route] (ecmascript)");
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
        pool = __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$mysql2$2f$promise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["default"].createPool({
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
"[project]/tailwind/src/features/line-dashboard/components/data-table/constants.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DEFAULT_RANGE_DAYS",
    ()=>DEFAULT_RANGE_DAYS,
    "DEFAULT_TABLE",
    ()=>DEFAULT_TABLE,
    "MIN_SAVING_VISIBLE_MS",
    ()=>MIN_SAVING_VISIBLE_MS,
    "SAVED_VISIBLE_MS",
    ()=>SAVED_VISIBLE_MS,
    "SAVING_DELAY_MS",
    ()=>SAVING_DELAY_MS,
    "STEP_COLUMN_KEYS",
    ()=>STEP_COLUMN_KEYS,
    "STEP_COLUMN_KEY_SET",
    ()=>STEP_COLUMN_KEY_SET,
    "dateFormatter",
    ()=>dateFormatter,
    "getDefaultFromValue",
    ()=>getDefaultFromValue,
    "getDefaultToValue",
    ()=>getDefaultToValue,
    "numberFormatter",
    ()=>numberFormatter,
    "timeFormatter",
    ()=>timeFormatter,
    "toDateInputValue",
    ()=>toDateInputValue
]);
const DEFAULT_TABLE = "drone_sop_v3";
const DEFAULT_RANGE_DAYS = 3;
const DAY_IN_MS = 86_400_000;
const toDateInputValue = (date)=>date.toISOString().split("T")[0];
const getDefaultFromValue = ()=>{
    const now = new Date();
    const from = new Date(now.getTime() - DEFAULT_RANGE_DAYS * DAY_IN_MS);
    return toDateInputValue(from);
};
const getDefaultToValue = ()=>toDateInputValue(new Date());
const SAVING_DELAY_MS = 180;
const MIN_SAVING_VISIBLE_MS = 500;
const SAVED_VISIBLE_MS = 800;
const STEP_COLUMN_KEYS = [
    "main_step",
    "metro_steps",
    "metro_current_step",
    "metro_end_step",
    "custom_end_step",
    "inform_step"
];
const STEP_COLUMN_KEY_SET = new Set(STEP_COLUMN_KEYS);
const numberFormatter = new Intl.NumberFormat("en-US");
const timeFormatter = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
});
const dateFormatter = new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
});
}),
"[project]/tailwind/src/features/line-dashboard/api/get-line-ids.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LINE_SDWT_TABLE_NAME",
    ()=>LINE_SDWT_TABLE_NAME,
    "getDistinctLineIds",
    ()=>getDistinctLineIds
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/db.js [app-route] (ecmascript)");
;
const LINE_SDWT_TABLE_NAME = "line_sdwt";
async function getDistinctLineIds() {
    const rows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
      SELECT DISTINCT line_id
      FROM \`${LINE_SDWT_TABLE_NAME}\`
      WHERE line_id IS NOT NULL AND line_id <> ''
      ORDER BY line_id
    `);
    return rows.map((row)=>row.line_id).filter((lineId)=>typeof lineId === "string" && lineId.length > 0);
}
}),
"[project]/tailwind/src/app/api/tables/route.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "GET",
    ()=>GET
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/server.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/db.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/data-table/constants.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$get$2d$line$2d$ids$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/get-line-ids.js [app-route] (ecmascript)");
;
;
;
;
const SAFE_IDENTIFIER = /^[A-Za-z0-9_]+$/;
const DATE_ONLY_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const ROW_LIMIT = 500;
const DATE_COLUMN_CANDIDATES = [
    "updated_at",
    "created_at",
    "timestamp",
    "ts",
    "date"
];
function sanitizeIdentifier(value, fallback = null) {
    if (typeof value !== "string") return fallback;
    const trimmed = value.trim();
    if (!SAFE_IDENTIFIER.test(trimmed)) return fallback;
    return trimmed;
}
function normalizeDateOnly(value) {
    if (typeof value !== "string") return null;
    const trimmed = value.trim();
    if (!DATE_ONLY_REGEX.test(trimmed)) return null;
    const parsed = new Date(`${trimmed}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime())) return null;
    return trimmed;
}
function findColumn(columnNames, target) {
    const targetLower = target.toLowerCase();
    for (const name of columnNames){
        if (typeof name !== "string") continue;
        if (name.toLowerCase() === targetLower) return name;
    }
    return null;
}
async function getUserSdwtProdForLine(lineId) {
    if (typeof lineId !== "string") return null;
    const trimmedLineId = lineId.trim();
    if (!trimmedLineId) return null;
    const rows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
      SELECT user_sdwt_prod
      FROM \`${__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$get$2d$line$2d$ids$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["LINE_SDWT_TABLE_NAME"]}\`
      WHERE line_id = ?
      ORDER BY user_sdwt_prod
      LIMIT 1
    `, [
        trimmedLineId
    ]);
    const value = rows?.[0]?.user_sdwt_prod;
    if (typeof value !== "string") return null;
    const trimmedValue = value.trim();
    return trimmedValue.length > 0 ? trimmedValue : null;
}
async function GET(request) {
    const url = new URL(request.url);
    const searchParams = url.searchParams;
    const tableParam = searchParams.get("table");
    const fromParam = searchParams.get("from");
    const toParam = searchParams.get("to");
    const lineIdParam = searchParams.get("lineId");
    const tableName = sanitizeIdentifier(tableParam, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["DEFAULT_TABLE"]);
    let normalizedFrom = normalizeDateOnly(fromParam);
    let normalizedTo = normalizeDateOnly(toParam);
    const normalizedLineId = typeof lineIdParam === "string" && lineIdParam.trim().length > 0 ? lineIdParam.trim() : null;
    if (normalizedFrom && normalizedTo) {
        const fromTime = new Date(`${normalizedFrom}T00:00:00Z`).getTime();
        const toTime = new Date(`${normalizedTo}T23:59:59Z`).getTime();
        if (Number.isFinite(fromTime) && Number.isFinite(toTime) && fromTime > toTime) {
            const temp = normalizedFrom;
            normalizedFrom = normalizedTo;
            normalizedTo = temp;
        }
    }
    try {
        const columnRows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`SHOW COLUMNS FROM \`${tableName}\``);
        const columnNames = columnRows.map((column)=>column?.Field).filter((value)=>typeof value === "string");
        const lineIdColumn = normalizedLineId ? findColumn(columnNames, "line_id") : null;
        const userSdwtProdColumn = normalizedLineId ? findColumn(columnNames, "user_sdwt_prod") : null;
        const dateColumn = (normalizedFrom || normalizedTo) && DATE_COLUMN_CANDIDATES.map((candidate)=>findColumn(columnNames, candidate)).find(Boolean);
        const filters = [];
        const params = [];
        if (normalizedLineId) {
            const mappedUserSdwtProd = userSdwtProdColumn ? await getUserSdwtProdForLine(normalizedLineId) : null;
            if (mappedUserSdwtProd && userSdwtProdColumn) {
                filters.push(`\`${userSdwtProdColumn}\` = ?`);
                params.push(mappedUserSdwtProd);
            } else if (lineIdColumn) {
                filters.push(`\`${lineIdColumn}\` = ?`);
                params.push(normalizedLineId);
            }
        }
        if (normalizedFrom && dateColumn) {
            filters.push(`\`${dateColumn}\` >= ?`);
            params.push(`${normalizedFrom} 00:00:00`);
        }
        if (normalizedTo && dateColumn) {
            filters.push(`\`${dateColumn}\` <= ?`);
            params.push(`${normalizedTo} 23:59:59`);
        }
        const whereClause = filters.length > 0 ? `WHERE ${filters.join(" AND ")}` : "";
        const orderColumn = dateColumn ?? findColumn(columnNames, "updated_at") ?? findColumn(columnNames, "created_at") ?? findColumn(columnNames, "id");
        const orderClause = orderColumn ? `ORDER BY \`${orderColumn}\` DESC` : "";
        const limit = Math.max(1, Math.min(ROW_LIMIT, Number.parseInt(searchParams.get("limit") ?? "", 10) || ROW_LIMIT));
        const rows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
        SELECT *
        FROM \`${tableName}\`
        ${whereClause}
        ${orderClause}
      `, params);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            table: tableName,
            from: normalizedFrom && dateColumn ? normalizedFrom : null,
            to: normalizedTo && dateColumn ? normalizedTo : null,
            rowCount: rows.length,
            columns: columnNames,
            rows
        });
    } catch (error) {
        if (error && typeof error === "object" && error.code === "ER_NO_SUCH_TABLE") {
            return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
                error: `Table "${tableName}" was not found`
            }, {
                status: 404
            });
        }
        console.error("Failed to load table data", error);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "Failed to load table data"
        }, {
            status: 500
        });
    }
}
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__62eedad4._.js.map