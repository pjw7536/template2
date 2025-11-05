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
"[project]/tailwind/src/features/line-dashboard/components/data-table/utils/constants.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/features/line-dashboard/components/data-table/utils/constants.js
// 데이터 테이블 전역에서 재사용하는 상수와 포맷터들입니다.
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
}),
"[project]/tailwind/src/features/line-dashboard/api/constants.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/features/line-dashboard/api/constants.js
// API 유틸 전반에서 공유하는 정규식/상수 모음입니다.
__turbopack_context__.s([
    "DATE_COLUMN_CANDIDATES",
    ()=>DATE_COLUMN_CANDIDATES,
    "DATE_ONLY_REGEX",
    ()=>DATE_ONLY_REGEX,
    "LINE_SDWT_TABLE_NAME",
    ()=>LINE_SDWT_TABLE_NAME,
    "SAFE_IDENTIFIER",
    ()=>SAFE_IDENTIFIER
]);
const SAFE_IDENTIFIER = /^[A-Za-z0-9_]+$/;
const DATE_ONLY_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const DATE_COLUMN_CANDIDATES = [
    "created_at",
    "updated_at",
    "timestamp",
    "ts",
    "date"
];
const LINE_SDWT_TABLE_NAME = "line_sdwt";
}),
"[project]/tailwind/src/features/line-dashboard/api/columns.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/features/line-dashboard/api/columns.js
__turbopack_context__.s([
    "findColumn",
    ()=>findColumn,
    "pickBaseTimestampColumn",
    ()=>pickBaseTimestampColumn
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/constants.js [app-route] (ecmascript)");
;
function findColumn(columnNames, target) {
    // 안전하게 배열 형태로 강제 변환 (null, undefined 방지)
    const list = Array.isArray(columnNames) ? columnNames : [];
    // 찾고 싶은 대상 문자열을 소문자로 통일
    const targetLower = String(target ?? "").toLowerCase();
    // 모든 컬럼 이름을 순회하며 비교
    for (const name of list){
        if (typeof name !== "string") continue; // 문자열이 아닌 값은 무시
        if (name.toLowerCase() === targetLower) return name // 일치하면 원래 이름 그대로 반환
        ;
    }
    // 끝까지 못 찾으면 null
    return null;
}
function pickBaseTimestampColumn(columnNames) {
    // 후보 목록을 순서대로 확인
    for (const candidate of __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["DATE_COLUMN_CANDIDATES"]){
        const found = findColumn(columnNames, candidate);
        if (found) return found // 첫 번째로 발견된 컬럼 반환
        ;
    }
    // 후보 중 아무 것도 없으면 null
    return null;
}
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

// src/lib/db.js
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
"[project]/tailwind/src/features/line-dashboard/api/lineFilters.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/features/line-dashboard/api/lineFilters.js
__turbopack_context__.s([
    "buildLineFilters",
    ()=>buildLineFilters
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/db.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/constants.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$columns$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/columns.js [app-route] (ecmascript)");
;
;
;
const USER_SDWT_PROD_LOOKUP_QUERY = `
  SELECT DISTINCT user_sdwt_prod
  FROM \`${__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["LINE_SDWT_TABLE_NAME"]}\`
  WHERE line_id = ?
    AND user_sdwt_prod IS NOT NULL
    AND user_sdwt_prod <> ''
`;
/**
 * 특정 line_id에 연결된 user_sdwt_prod 목록 조회
 * - 문자열만 추려서 trim 후 중복 제거(Set)
 */ async function getUserSdwtProdValues(lineId) {
    const rows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(USER_SDWT_PROD_LOOKUP_QUERY, [
        lineId
    ]);
    const set = new Set();
    for (const r of rows || []){
        const v = typeof r?.user_sdwt_prod === "string" ? r.user_sdwt_prod.trim() : "";
        if (v) set.add(v);
    }
    return Array.from(set);
}
async function buildLineFilters(columnNames, lineId) {
    const filters = [];
    const params = [];
    // lineId가 없으면 필터 없이 종료
    if (!lineId) return {
        filters,
        params
    };
    // 1) user_sdwt_prod 우선 사용
    const usdwtCol = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$columns$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["findColumn"])(columnNames, "user_sdwt_prod");
    if (usdwtCol) {
        const values = await getUserSdwtProdValues(lineId);
        if (values.length > 0) {
            const placeholders = values.map(()=>"?").join(", ");
            filters.push(`\`${usdwtCol}\` IN (${placeholders})`);
            params.push(...values);
            return {
                filters,
                params
            };
        }
    }
    // 2) 폴백: line_id = ?
    const lineCol = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$columns$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["findColumn"])(columnNames, "line_id");
    if (lineCol) {
        filters.push(`\`${lineCol}\` = ?`);
        params.push(lineId);
    }
    return {
        filters,
        params
    };
}
}),
"[project]/tailwind/src/features/line-dashboard/api/validation.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/features/line-dashboard/api/validation.js
__turbopack_context__.s([
    "normalizeDateOnly",
    ()=>normalizeDateOnly,
    "sanitizeIdentifier",
    ()=>sanitizeIdentifier
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/constants.js [app-route] (ecmascript)");
;
function sanitizeIdentifier(value, fallback = null) {
    if (typeof value !== "string") return fallback;
    const trimmed = value.trim();
    return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["SAFE_IDENTIFIER"].test(trimmed) ? trimmed : fallback;
}
function normalizeDateOnly(value) {
    if (typeof value !== "string") return null;
    const trimmed = value.trim();
    return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["DATE_ONLY_REGEX"].test(trimmed) ? trimmed : null;
}
}),
"[project]/tailwind/src/app/api/esop-history/route.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/app/api/esop-history/route.js
__turbopack_context__.s([
    "GET",
    ()=>GET
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/server.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$utils$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/components/data-table/utils/constants.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$columns$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/columns.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$lineFilters$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/lineFilters.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$validation$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/features/line-dashboard/api/validation.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/db.js [app-route] (ecmascript)");
;
;
;
;
;
;
const DAY_IN_MS = 86_400_000;
const DEFAULT_HISTORY_DAYS = 30;
const EMPTY_BUCKET_KEY = "__@@EMPTY@@__";
const CATEGORY_CONFIG = [
    {
        key: "sdwt",
        column: "sdwt",
        label: "SDWT"
    },
    {
        key: "user_sdwt",
        column: "user_sdwt",
        label: "User SDWT"
    },
    {
        key: "eqp_id",
        column: "eqp_id",
        label: "Equipment"
    },
    {
        key: "main_step",
        column: "main_step",
        label: "Main Step"
    },
    {
        key: "sample_type",
        column: "sample_type",
        label: "Sample Type"
    },
    {
        key: "line_id",
        column: "line_id",
        label: "Line ID"
    }
];
function toDateOnly(value) {
    return value.toISOString().split("T")[0];
}
function createDefaultRange() {
    const end = new Date();
    const start = new Date(end.getTime() - (DEFAULT_HISTORY_DAYS - 1) * DAY_IN_MS);
    return {
        from: toDateOnly(start),
        to: toDateOnly(end)
    };
}
function createSendJiraCase(column) {
    const col = `\`${column}\``;
    return `(
    CASE
      WHEN ${col} IS NULL THEN 0
      WHEN CAST(${col} AS SIGNED) > 0 THEN 1
      WHEN LOWER(CAST(${col} AS CHAR)) IN ('1', 'y', 'yes', 'true', 't', 'on') THEN 1
      ELSE 0
    END
  )`;
}
function createWhereClause(baseTimestampColumn, normalizedFrom, normalizedTo, lineFilters, lineParams) {
    const filters = [
        ...lineFilters
    ];
    const params = [
        ...lineParams
    ];
    if (normalizedFrom) {
        params.push(`${normalizedFrom} 00:00:00`);
        filters.push(`\`${baseTimestampColumn}\` >= ?`);
    }
    if (normalizedTo) {
        params.push(`${normalizedTo} 23:59:59`);
        filters.push(`\`${baseTimestampColumn}\` <= ?`);
    }
    return {
        whereClause: filters.length ? `WHERE ${filters.join(" AND ")}` : "",
        params
    };
}
function ensureAscendingRange(from, to) {
    if (!from || !to) return {
        from,
        to
    };
    const fromMs = Date.parse(`${from}T00:00:00Z`);
    const toMs = Date.parse(`${to}T23:59:59Z`);
    if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || fromMs <= toMs) {
        return {
            from,
            to
        };
    }
    return {
        from: to,
        to: from
    };
}
function normalizeBucketLabel(value) {
    if (!value || value === EMPTY_BUCKET_KEY) return "미지정";
    return value;
}
async function GET(request) {
    const url = new URL(request.url);
    const searchParams = url.searchParams;
    const tableParam = searchParams.get("table");
    const fromParam = searchParams.get("from");
    const toParam = searchParams.get("to");
    const lineIdParam = searchParams.get("lineId");
    const tableName = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$validation$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["sanitizeIdentifier"])(tableParam, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$components$2f$data$2d$table$2f$utils$2f$constants$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["DEFAULT_TABLE"]);
    if (!tableName) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "Invalid table name"
        }, {
            status: 400
        });
    }
    let normalizedFrom = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$validation$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["normalizeDateOnly"])(fromParam);
    let normalizedTo = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$validation$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["normalizeDateOnly"])(toParam);
    if (!normalizedFrom && !normalizedTo) {
        const defaults = createDefaultRange();
        normalizedFrom = defaults.from;
        normalizedTo = defaults.to;
    }
    ;
    ({ from: normalizedFrom, to: normalizedTo } = ensureAscendingRange(normalizedFrom, normalizedTo));
    const normalizedLineId = typeof lineIdParam === "string" && lineIdParam.trim().length > 0 ? lineIdParam.trim() : null;
    try {
        const columnRows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`SHOW COLUMNS FROM \`${tableName}\``);
        const columnNames = columnRows.map((column)=>column?.Field).filter((name)=>typeof name === "string");
        if (columnNames.length === 0) {
            return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
                error: `Table "${tableName}" has no columns`
            }, {
                status: 400
            });
        }
        const baseTimestampColumn = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$columns$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["pickBaseTimestampColumn"])(columnNames);
        if (!baseTimestampColumn) {
            return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
                error: `No timestamp-like column found in "${tableName}".`
            }, {
                status: 400
            });
        }
        const { filters: lineFilters, params: lineParams, earlyEmpty } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$lineFilters$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["buildLineFilters"])(columnNames, normalizedLineId);
        if (earlyEmpty) {
            return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
                table: tableName,
                lineId: normalizedLineId,
                from: normalizedFrom,
                to: normalizedTo,
                dates: [],
                totals: [],
                aggregate: {
                    totalRows: 0,
                    sendJiraRows: 0
                },
                breakdowns: CATEGORY_CONFIG.map((config)=>({
                        key: config.key,
                        label: config.label,
                        available: false,
                        column: null,
                        series: []
                    })),
                generatedAt: new Date().toISOString()
            });
        }
        const { whereClause, params: baseParams } = createWhereClause(baseTimestampColumn, normalizedFrom, normalizedTo, lineFilters, lineParams);
        const workDateExpression = `DATE(CONVERT_TZ(\`${baseTimestampColumn}\`, 'UTC', '+09:00'))`;
        const sendJiraColumn = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$columns$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["findColumn"])(columnNames, "send_jira");
        const sendJiraSelect = sendJiraColumn ? `, SUM(${createSendJiraCase(sendJiraColumn)}) AS send_jira_count` : `, 0 AS send_jira_count`;
        const totalsQuery = `
      SELECT
        ${workDateExpression} AS work_date,
        COUNT(*) AS total_rows
        ${sendJiraSelect}
      FROM \`${tableName}\`
      ${whereClause}
      GROUP BY work_date
      ORDER BY work_date ASC
    `;
        const totalsRows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(totalsQuery, [
            ...baseParams
        ]);
        const dateSet = new Set();
        const totalsByDate = new Map();
        for (const row of totalsRows || []){
            const dateKey = row?.work_date;
            if (!dateKey) continue;
            dateSet.add(dateKey);
            const total = Number(row?.total_rows) || 0;
            const sendJira = Number(row?.send_jira_count) || 0;
            totalsByDate.set(dateKey, {
                total,
                sendJira
            });
        }
        const breakdowns = [];
        for (const config of CATEGORY_CONFIG){
            const column = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$features$2f$line$2d$dashboard$2f$api$2f$columns$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["findColumn"])(columnNames, config.column);
            if (!column) {
                breakdowns.push({
                    key: config.key,
                    label: config.label,
                    available: false,
                    column: null,
                    series: []
                });
                continue;
            }
            const breakdownQuery = `
        SELECT
          ${workDateExpression} AS work_date,
          COALESCE(NULLIF(TRIM(CAST(\`${column}\` AS CHAR)), ''), '${EMPTY_BUCKET_KEY}') AS bucket_value,
          COUNT(*) AS bucket_count
        FROM \`${tableName}\`
        ${whereClause}
        GROUP BY work_date, bucket_value
        ORDER BY work_date ASC, bucket_value ASC
      `;
            const rows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(breakdownQuery, [
                ...baseParams
            ]);
            const bucketMap = new Map();
            for (const row of rows || []){
                const dateKey = row?.work_date;
                if (dateKey) {
                    dateSet.add(dateKey);
                }
                const rawBucket = row?.bucket_value || EMPTY_BUCKET_KEY;
                const bucketKey = rawBucket || EMPTY_BUCKET_KEY;
                const bucketCount = Number(row?.bucket_count) || 0;
                let entry = bucketMap.get(bucketKey);
                if (!entry) {
                    entry = {
                        key: bucketKey,
                        label: normalizeBucketLabel(bucketKey),
                        total: 0,
                        values: new Map()
                    };
                    bucketMap.set(bucketKey, entry);
                }
                entry.total += bucketCount;
                if (dateKey) {
                    const previous = entry.values.get(dateKey) || 0;
                    entry.values.set(dateKey, previous + bucketCount);
                }
            }
            const series = Array.from(bucketMap.values()).map((entry)=>({
                    key: entry.key,
                    label: entry.label,
                    total: entry.total,
                    data: [],
                    valueMap: entry.values
                })).sort((a, b)=>{
                if (b.total !== a.total) return b.total - a.total;
                return a.label.localeCompare(b.label);
            }).map((entry)=>({
                    key: entry.key,
                    label: entry.label,
                    total: entry.total,
                    data: entry.data,
                    valueMap: entry.valueMap
                }));
            breakdowns.push({
                key: config.key,
                label: config.label,
                available: true,
                column,
                series
            });
        }
        const sortedDates = Array.from(dateSet).sort();
        const totals = sortedDates.map((dateKey)=>{
            const entry = totalsByDate.get(dateKey);
            return {
                date: dateKey,
                totalCount: entry ? entry.total : 0,
                sendJiraCount: entry ? entry.sendJira : 0
            };
        });
        let totalRowsSum = 0;
        let sendJiraSum = 0;
        for (const item of totals){
            totalRowsSum += item.totalCount;
            sendJiraSum += item.sendJiraCount;
        }
        for (const breakdown of breakdowns){
            if (!breakdown.available) continue;
            breakdown.series = breakdown.series.map((series)=>({
                    key: series.key,
                    label: series.label,
                    total: series.total,
                    data: sortedDates.map((dateKey)=>({
                            date: dateKey,
                            value: series.valueMap.get(dateKey) || 0
                        }))
                }));
        }
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            table: tableName,
            lineId: normalizedLineId,
            from: normalizedFrom,
            to: normalizedTo,
            dates: sortedDates,
            totals,
            aggregate: {
                totalRows: totalRowsSum,
                sendJiraRows: sendJiraSum
            },
            breakdowns,
            generatedAt: new Date().toISOString()
        });
    } catch (error) {
        if (error && typeof error === "object" && error.code === "ER_NO_SUCH_TABLE") {
            return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
                error: `Table "${tableName}" was not found`
            }, {
                status: 404
            });
        }
        console.error("Failed to load ESOP history", error);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "Failed to load ESOP history"
        }, {
            status: 500
        });
    }
}
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__1162a0af._.js.map