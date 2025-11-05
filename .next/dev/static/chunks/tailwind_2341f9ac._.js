(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/tailwind/src/components/ui/breadcrumb.jsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Breadcrumb",
    ()=>Breadcrumb,
    "BreadcrumbEllipsis",
    ()=>BreadcrumbEllipsis,
    "BreadcrumbItem",
    ()=>BreadcrumbItem,
    "BreadcrumbLink",
    ()=>BreadcrumbLink,
    "BreadcrumbList",
    ()=>BreadcrumbList,
    "BreadcrumbPage",
    ()=>BreadcrumbPage,
    "BreadcrumbSeparator",
    ()=>BreadcrumbSeparator
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/@radix-ui/react-slot/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronRight$3e$__ = __turbopack_context__.i("[project]/tailwind/node_modules/lucide-react/dist/esm/icons/chevron-right.js [app-client] (ecmascript) <export default as ChevronRight>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$ellipsis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__MoreHorizontal$3e$__ = __turbopack_context__.i("[project]/tailwind/node_modules/lucide-react/dist/esm/icons/ellipsis.js [app-client] (ecmascript) <export default as MoreHorizontal>");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/lib/utils.js [app-client] (ecmascript)");
;
;
;
;
;
;
function Breadcrumb(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(5);
    if ($[0] !== "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f") {
        for(let $i = 0; $i < 5; $i += 1){
            $[$i] = Symbol.for("react.memo_cache_sentinel");
        }
        $[0] = "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f";
    }
    let props;
    if ($[1] !== t0) {
        ({ ...props } = t0);
        $[1] = t0;
        $[2] = props;
    } else {
        props = $[2];
    }
    let t1;
    if ($[3] !== props) {
        t1 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("nav", {
            "aria-label": "breadcrumb",
            "data-slot": "breadcrumb",
            ...props
        }, void 0, false, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 26,
            columnNumber: 10
        }, this);
        $[3] = props;
        $[4] = t1;
    } else {
        t1 = $[4];
    }
    return t1;
}
_c = Breadcrumb;
function BreadcrumbList(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(9);
    if ($[0] !== "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f") {
        for(let $i = 0; $i < 9; $i += 1){
            $[$i] = Symbol.for("react.memo_cache_sentinel");
        }
        $[0] = "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f";
    }
    let className;
    let props;
    if ($[1] !== t0) {
        ({ className, ...props } = t0);
        $[1] = t0;
        $[2] = className;
        $[3] = props;
    } else {
        className = $[2];
        props = $[3];
    }
    let t1;
    if ($[4] !== className) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])("text-muted-foreground flex flex-wrap items-center gap-1.5 text-sm break-words sm:gap-2.5", className);
        $[4] = className;
        $[5] = t1;
    } else {
        t1 = $[5];
    }
    let t2;
    if ($[6] !== props || $[7] !== t1) {
        t2 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("ol", {
            "data-slot": "breadcrumb-list",
            className: t1,
            ...props
        }, void 0, false, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 66,
            columnNumber: 10
        }, this);
        $[6] = props;
        $[7] = t1;
        $[8] = t2;
    } else {
        t2 = $[8];
    }
    return t2;
}
_c1 = BreadcrumbList;
function BreadcrumbItem(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(9);
    if ($[0] !== "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f") {
        for(let $i = 0; $i < 9; $i += 1){
            $[$i] = Symbol.for("react.memo_cache_sentinel");
        }
        $[0] = "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f";
    }
    let className;
    let props;
    if ($[1] !== t0) {
        ({ className, ...props } = t0);
        $[1] = t0;
        $[2] = className;
        $[3] = props;
    } else {
        className = $[2];
        props = $[3];
    }
    let t1;
    if ($[4] !== className) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])("inline-flex items-center gap-1.5", className);
        $[4] = className;
        $[5] = t1;
    } else {
        t1 = $[5];
    }
    let t2;
    if ($[6] !== props || $[7] !== t1) {
        t2 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
            "data-slot": "breadcrumb-item",
            className: t1,
            ...props
        }, void 0, false, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 107,
            columnNumber: 10
        }, this);
        $[6] = props;
        $[7] = t1;
        $[8] = t2;
    } else {
        t2 = $[8];
    }
    return t2;
}
_c2 = BreadcrumbItem;
function BreadcrumbLink(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(11);
    if ($[0] !== "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f") {
        for(let $i = 0; $i < 11; $i += 1){
            $[$i] = Symbol.for("react.memo_cache_sentinel");
        }
        $[0] = "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f";
    }
    let asChild;
    let className;
    let props;
    if ($[1] !== t0) {
        ({ asChild, className, ...props } = t0);
        $[1] = t0;
        $[2] = asChild;
        $[3] = className;
        $[4] = props;
    } else {
        asChild = $[2];
        className = $[3];
        props = $[4];
    }
    const Comp = asChild ? __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Slot"] : "a";
    let t1;
    if ($[5] !== className) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])("hover:text-foreground transition-colors", className);
        $[5] = className;
        $[6] = t1;
    } else {
        t1 = $[6];
    }
    let t2;
    if ($[7] !== Comp || $[8] !== props || $[9] !== t1) {
        t2 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Comp, {
            "data-slot": "breadcrumb-link",
            className: t1,
            ...props
        }, void 0, false, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 153,
            columnNumber: 10
        }, this);
        $[7] = Comp;
        $[8] = props;
        $[9] = t1;
        $[10] = t2;
    } else {
        t2 = $[10];
    }
    return t2;
}
_c3 = BreadcrumbLink;
function BreadcrumbPage(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(9);
    if ($[0] !== "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f") {
        for(let $i = 0; $i < 9; $i += 1){
            $[$i] = Symbol.for("react.memo_cache_sentinel");
        }
        $[0] = "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f";
    }
    let className;
    let props;
    if ($[1] !== t0) {
        ({ className, ...props } = t0);
        $[1] = t0;
        $[2] = className;
        $[3] = props;
    } else {
        className = $[2];
        props = $[3];
    }
    let t1;
    if ($[4] !== className) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])("text-foreground font-normal", className);
        $[4] = className;
        $[5] = t1;
    } else {
        t1 = $[5];
    }
    let t2;
    if ($[6] !== props || $[7] !== t1) {
        t2 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
            "data-slot": "breadcrumb-page",
            role: "link",
            "aria-disabled": "true",
            "aria-current": "page",
            className: t1,
            ...props
        }, void 0, false, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 195,
            columnNumber: 10
        }, this);
        $[6] = props;
        $[7] = t1;
        $[8] = t2;
    } else {
        t2 = $[8];
    }
    return t2;
}
_c4 = BreadcrumbPage;
function BreadcrumbSeparator(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(13);
    if ($[0] !== "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f") {
        for(let $i = 0; $i < 13; $i += 1){
            $[$i] = Symbol.for("react.memo_cache_sentinel");
        }
        $[0] = "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f";
    }
    let children;
    let className;
    let props;
    if ($[1] !== t0) {
        ({ children, className, ...props } = t0);
        $[1] = t0;
        $[2] = children;
        $[3] = className;
        $[4] = props;
    } else {
        children = $[2];
        className = $[3];
        props = $[4];
    }
    let t1;
    if ($[5] !== className) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])("[&>svg]:size-3.5", className);
        $[5] = className;
        $[6] = t1;
    } else {
        t1 = $[6];
    }
    let t2;
    if ($[7] !== children) {
        t2 = children ?? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$chevron$2d$right$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__ChevronRight$3e$__["ChevronRight"], {}, void 0, false, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 240,
            columnNumber: 22
        }, this);
        $[7] = children;
        $[8] = t2;
    } else {
        t2 = $[8];
    }
    let t3;
    if ($[9] !== props || $[10] !== t1 || $[11] !== t2) {
        t3 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
            "data-slot": "breadcrumb-separator",
            role: "presentation",
            "aria-hidden": "true",
            className: t1,
            ...props,
            children: t2
        }, void 0, false, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 248,
            columnNumber: 10
        }, this);
        $[9] = props;
        $[10] = t1;
        $[11] = t2;
        $[12] = t3;
    } else {
        t3 = $[12];
    }
    return t3;
}
_c5 = BreadcrumbSeparator;
function BreadcrumbEllipsis(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(11);
    if ($[0] !== "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f") {
        for(let $i = 0; $i < 11; $i += 1){
            $[$i] = Symbol.for("react.memo_cache_sentinel");
        }
        $[0] = "6a26670ed82aa33c88719322df2863f21b9a1424c3e671a1fb8b0e9e513a205f";
    }
    let className;
    let props;
    if ($[1] !== t0) {
        ({ className, ...props } = t0);
        $[1] = t0;
        $[2] = className;
        $[3] = props;
    } else {
        className = $[2];
        props = $[3];
    }
    let t1;
    if ($[4] !== className) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])("flex size-9 items-center justify-center", className);
        $[4] = className;
        $[5] = t1;
    } else {
        t1 = $[5];
    }
    let t2;
    let t3;
    if ($[6] === Symbol.for("react.memo_cache_sentinel")) {
        t2 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$ellipsis$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__MoreHorizontal$3e$__["MoreHorizontal"], {
            className: "size-4"
        }, void 0, false, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 291,
            columnNumber: 10
        }, this);
        t3 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
            className: "sr-only",
            children: "More"
        }, void 0, false, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 292,
            columnNumber: 10
        }, this);
        $[6] = t2;
        $[7] = t3;
    } else {
        t2 = $[6];
        t3 = $[7];
    }
    let t4;
    if ($[8] !== props || $[9] !== t1) {
        t4 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
            "data-slot": "breadcrumb-ellipsis",
            role: "presentation",
            "aria-hidden": "true",
            className: t1,
            ...props,
            children: [
                t2,
                t3
            ]
        }, void 0, true, {
            fileName: "[project]/tailwind/src/components/ui/breadcrumb.jsx",
            lineNumber: 301,
            columnNumber: 10
        }, this);
        $[8] = props;
        $[9] = t1;
        $[10] = t4;
    } else {
        t4 = $[10];
    }
    return t4;
}
_c6 = BreadcrumbEllipsis;
;
var _c, _c1, _c2, _c3, _c4, _c5, _c6;
__turbopack_context__.k.register(_c, "Breadcrumb");
__turbopack_context__.k.register(_c1, "BreadcrumbList");
__turbopack_context__.k.register(_c2, "BreadcrumbItem");
__turbopack_context__.k.register(_c3, "BreadcrumbLink");
__turbopack_context__.k.register(_c4, "BreadcrumbPage");
__turbopack_context__.k.register(_c5, "BreadcrumbSeparator");
__turbopack_context__.k.register(_c6, "BreadcrumbEllipsis");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/tailwind/src/components/navigation/dynamic-breadcrumb.jsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DynamicBreadcrumb",
    ()=>DynamicBreadcrumb
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/next/navigation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$components$2f$ui$2f$breadcrumb$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/src/components/ui/breadcrumb.jsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
'use client';
;
;
;
;
function toTitleCase(segment) {
    return decodeURIComponent(segment).replace(/-/g, " ").replace(/\b\w/g, (char)=>char.toUpperCase());
}
function DynamicBreadcrumb(t0) {
    _s();
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(15);
    if ($[0] !== "4f1ad18308795724ba37012771d175cb2ee24320052eb809e667f38c24edb2a9") {
        for(let $i = 0; $i < 15; $i += 1){
            $[$i] = Symbol.for("react.memo_cache_sentinel");
        }
        $[0] = "4f1ad18308795724ba37012771d175cb2ee24320052eb809e667f38c24edb2a9";
    }
    const { overrides: t1 } = t0;
    let t2;
    if ($[1] !== t1) {
        t2 = t1 === undefined ? {} : t1;
        $[1] = t1;
        $[2] = t2;
    } else {
        t2 = $[2];
    }
    const overrides = t2;
    const pathname = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePathname"])();
    let t3;
    bb0: {
        if (!pathname) {
            let t4;
            if ($[3] === Symbol.for("react.memo_cache_sentinel")) {
                t4 = [];
                $[3] = t4;
            } else {
                t4 = $[3];
            }
            t3 = t4;
            break bb0;
        }
        let t4;
        if ($[4] !== pathname) {
            t4 = pathname.split("/").filter(Boolean);
            $[4] = pathname;
            $[5] = t4;
        } else {
            t4 = $[5];
        }
        t3 = t4;
    }
    const segments = t3;
    let t4;
    if ($[6] !== overrides || $[7] !== segments) {
        t4 = segments.map({
            "DynamicBreadcrumb[segments.map()]": (segment, index)=>{
                const href = `/${segments.slice(0, index + 1).join("/")}`;
                const label = overrides[segment] ?? toTitleCase(segment);
                return {
                    href,
                    segment,
                    label
                };
            }
        }["DynamicBreadcrumb[segments.map()]"]);
        $[6] = overrides;
        $[7] = segments;
        $[8] = t4;
    } else {
        t4 = $[8];
    }
    const crumbs = t4;
    if (crumbs.length === 0) {
        return null;
    }
    let t5;
    if ($[9] !== crumbs) {
        let t6;
        if ($[11] !== crumbs.length) {
            t6 = ({
                "DynamicBreadcrumb[crumbs.map()]": (crumb, index_0)=>{
                    const isLast = index_0 === crumbs.length - 1;
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                        children: [
                            index_0 > 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$components$2f$ui$2f$breadcrumb$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BreadcrumbSeparator"], {}, void 0, false, {
                                fileName: "[project]/tailwind/src/components/navigation/dynamic-breadcrumb.jsx",
                                lineNumber: 85,
                                columnNumber: 61
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$components$2f$ui$2f$breadcrumb$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BreadcrumbItem"], {
                                children: isLast ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$components$2f$ui$2f$breadcrumb$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BreadcrumbPage"], {
                                    children: crumb.label
                                }, void 0, false, {
                                    fileName: "[project]/tailwind/src/components/navigation/dynamic-breadcrumb.jsx",
                                    lineNumber: 85,
                                    columnNumber: 111
                                }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    className: "text-muted-foreground",
                                    children: crumb.label
                                }, void 0, false, {
                                    fileName: "[project]/tailwind/src/components/navigation/dynamic-breadcrumb.jsx",
                                    lineNumber: 85,
                                    columnNumber: 160
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/tailwind/src/components/navigation/dynamic-breadcrumb.jsx",
                                lineNumber: 85,
                                columnNumber: 85
                            }, this)
                        ]
                    }, crumb.href, true, {
                        fileName: "[project]/tailwind/src/components/navigation/dynamic-breadcrumb.jsx",
                        lineNumber: 85,
                        columnNumber: 18
                    }, this);
                }
            })["DynamicBreadcrumb[crumbs.map()]"];
            $[11] = crumbs.length;
            $[12] = t6;
        } else {
            t6 = $[12];
        }
        t5 = crumbs.map(t6);
        $[9] = crumbs;
        $[10] = t5;
    } else {
        t5 = $[10];
    }
    let t6;
    if ($[13] !== t5) {
        t6 = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$components$2f$ui$2f$breadcrumb$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Breadcrumb"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$src$2f$components$2f$ui$2f$breadcrumb$2e$jsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BreadcrumbList"], {
                children: t5
            }, void 0, false, {
                fileName: "[project]/tailwind/src/components/navigation/dynamic-breadcrumb.jsx",
                lineNumber: 101,
                columnNumber: 22
            }, this)
        }, void 0, false, {
            fileName: "[project]/tailwind/src/components/navigation/dynamic-breadcrumb.jsx",
            lineNumber: 101,
            columnNumber: 10
        }, this);
        $[13] = t5;
        $[14] = t6;
    } else {
        t6 = $[14];
    }
    return t6;
}
_s(DynamicBreadcrumb, "xbyQPtUVMO7MNj7WjJlpdWqRcTo=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePathname"]
    ];
});
_c = DynamicBreadcrumb;
var _c;
__turbopack_context__.k.register(_c, "DynamicBreadcrumb");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/tailwind/node_modules/next/navigation.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

module.exports = __turbopack_context__.r("[project]/tailwind/node_modules/next/dist/client/components/navigation.js [app-client] (ecmascript)");
}),
]);

//# sourceMappingURL=tailwind_2341f9ac._.js.map