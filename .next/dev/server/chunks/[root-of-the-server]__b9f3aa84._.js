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
"[project]/tailwind/src/app/api/drone-early-inform-v3/route.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// src/app/api/drone-early-inform-v3/route.js
__turbopack_context__.s([
    "GET",
    ()=>GET,
    "POST",
    ()=>POST
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/server.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/db.js [app-route] (ecmascript)");
;
;
const TABLE_NAME = "drone_early_inform_v3";
const SELECT_COLUMNS = [
    "id",
    "line_id",
    "main_step",
    "custom_end_step"
];
function normalizeLineId(value) {
    if (typeof value !== "string") return null;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}
function normalizeStep(value) {
    if (typeof value !== "string") return null;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}
function normalizeOptionalStep(value) {
    if (value === null || value === undefined) return null;
    if (typeof value !== "string") return String(value);
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}
async function GET(request) {
    const url = new URL(request.url);
    const lineIdParam = url.searchParams.get("lineId");
    const normalizedLineId = normalizeLineId(lineIdParam);
    try {
        const params = [];
        const where = [];
        if (normalizedLineId) {
            where.push("`line_id` = ?");
            params.push(normalizedLineId);
        }
        const whereClause = where.length ? `WHERE ${where.join(" AND ")}` : "";
        const rows = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
        SELECT ${SELECT_COLUMNS.map((column)=>`\`${column}\``).join(", ")}
        FROM \`${TABLE_NAME}\`
        ${whereClause}
        ORDER BY \`line_id\` ASC, \`main_step\` ASC, \`id\` ASC
      `, params);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            rows,
            lineId: normalizedLineId,
            count: rows.length
        });
    } catch (error) {
        console.error("Failed to load drone_early_inform_v3 rows", error);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "Failed to load table data"
        }, {
            status: 500
        });
    }
}
async function POST(request) {
    let payload;
    try {
        payload = await request.json();
    } catch  {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "Invalid JSON body"
        }, {
            status: 400
        });
    }
    const lineId = normalizeLineId(payload?.line_id ?? payload?.lineId);
    const mainStep = normalizeStep(payload?.main_step ?? payload?.mainStep);
    const customEndStep = normalizeOptionalStep(payload?.custom_end_step ?? payload?.customEndStep);
    if (!lineId) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "line_id is required"
        }, {
            status: 400
        });
    }
    if (!mainStep) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "main_step is required"
        }, {
            status: 400
        });
    }
    try {
        const pool = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getPool"])();
        const [result] = await pool.execute(`
        INSERT INTO \`${TABLE_NAME}\` (\`line_id\`, \`main_step\`, \`custom_end_step\`)
        VALUES (?, ?, ?)
      `, [
            lineId,
            mainStep,
            customEndStep
        ]);
        const insertedId = result?.insertId;
        if (!insertedId) {
            return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
                error: "Failed to insert row"
            }, {
                status: 500
            });
        }
        const [insertedRow] = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$db$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["runQuery"])(`
        SELECT ${SELECT_COLUMNS.map((column)=>`\`${column}\``).join(", ")}
        FROM \`${TABLE_NAME}\`
        WHERE \`id\` = ?
        LIMIT 1
      `, [
            insertedId
        ]);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            row: insertedRow
        }, {
            status: 201
        });
    } catch (error) {
        if (error && typeof error === "object" && error.code === "ER_DUP_ENTRY") {
            return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
                error: "A record with the same line_id and main_step already exists"
            }, {
                status: 409
            });
        }
        console.error("Failed to insert drone_early_inform_v3 row", error);
        return __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$server$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["NextResponse"].json({
            error: "Failed to insert row"
        }, {
            status: 500
        });
    }
}
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__b9f3aa84._.js.map