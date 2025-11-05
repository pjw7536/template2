module.exports = [
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/defaultAttributes.mjs [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * @license @tabler/icons-react v3.35.0 - MIT
 *
 * This source code is licensed under the MIT license.
 * See the LICENSE file in the root directory of this source tree.
 */ __turbopack_context__.s([
    "default",
    ()=>defaultAttributes
]);
var defaultAttributes = {
    outline: {
        xmlns: "http://www.w3.org/2000/svg",
        width: 24,
        height: 24,
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: 2,
        strokeLinecap: "round",
        strokeLinejoin: "round"
    },
    filled: {
        xmlns: "http://www.w3.org/2000/svg",
        width: 24,
        height: 24,
        viewBox: "0 0 24 24",
        fill: "currentColor",
        stroke: "none"
    }
};
;
 //# sourceMappingURL=defaultAttributes.mjs.map
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/createReactComponent.mjs [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * @license @tabler/icons-react v3.35.0 - MIT
 *
 * This source code is licensed under the MIT license.
 * See the LICENSE file in the root directory of this source tree.
 */ __turbopack_context__.s([
    "default",
    ()=>createReactComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/next@16.0.1_@babel+core@7.28.5_babel-plugin-react-compiler@1.0.0_react-dom@19.2.0_react@19.2.0__react@19.2.0/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$defaultAttributes$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/defaultAttributes.mjs [app-ssr] (ecmascript)");
;
;
const createReactComponent = (type, iconName, iconNamePascal, iconNode)=>{
    const Component = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["forwardRef"])(({ color = "currentColor", size = 24, stroke = 2, title, className, children, ...rest }, ref)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["createElement"])("svg", {
            ref,
            ...__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$defaultAttributes$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"][type],
            width: size,
            height: size,
            className: [
                `tabler-icon`,
                `tabler-icon-${iconName}`,
                className
            ].join(" "),
            ...type === "filled" ? {
                fill: color
            } : {
                strokeWidth: stroke,
                stroke: color
            },
            ...rest
        }, [
            title && (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["createElement"])("title", {
                key: "svg-title"
            }, title),
            ...iconNode.map(([tag, attrs])=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f$next$40$16$2e$0$2e$1_$40$babel$2b$core$40$7$2e$28$2e$5_babel$2d$plugin$2d$react$2d$compiler$40$1$2e$0$2e$0_react$2d$dom$40$19$2e$2$2e$0_react$40$19$2e$2$2e$0_$5f$react$40$19$2e$2$2e$0$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["createElement"])(tag, attrs)),
            ...Array.isArray(children) ? children : [
                children
            ]
        ]));
    Component.displayName = `${iconNamePascal}`;
    return Component;
};
;
 //# sourceMappingURL=createReactComponent.mjs.map
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconAlertCircle.mjs [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * @license @tabler/icons-react v3.35.0 - MIT
 *
 * This source code is licensed under the MIT license.
 * See the LICENSE file in the root directory of this source tree.
 */ __turbopack_context__.s([
    "__iconNode",
    ()=>__iconNode,
    "default",
    ()=>IconAlertCircle
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/createReactComponent.mjs [app-ssr] (ecmascript)");
;
const __iconNode = [
    [
        "path",
        {
            "d": "M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0",
            "key": "svg-0"
        }
    ],
    [
        "path",
        {
            "d": "M12 8v4",
            "key": "svg-1"
        }
    ],
    [
        "path",
        {
            "d": "M12 16h.01",
            "key": "svg-2"
        }
    ]
];
const IconAlertCircle = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"])("outline", "alert-circle", "AlertCircle", __iconNode);
;
 //# sourceMappingURL=IconAlertCircle.mjs.map
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconAlertCircle.mjs [app-ssr] (ecmascript) <export default as IconAlertCircle>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "IconAlertCircle",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconAlertCircle$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconAlertCircle$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconAlertCircle.mjs [app-ssr] (ecmascript)");
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconDeviceFloppy.mjs [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * @license @tabler/icons-react v3.35.0 - MIT
 *
 * This source code is licensed under the MIT license.
 * See the LICENSE file in the root directory of this source tree.
 */ __turbopack_context__.s([
    "__iconNode",
    ()=>__iconNode,
    "default",
    ()=>IconDeviceFloppy
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/createReactComponent.mjs [app-ssr] (ecmascript)");
;
const __iconNode = [
    [
        "path",
        {
            "d": "M6 4h10l4 4v10a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2",
            "key": "svg-0"
        }
    ],
    [
        "path",
        {
            "d": "M12 14m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0",
            "key": "svg-1"
        }
    ],
    [
        "path",
        {
            "d": "M14 4l0 4l-6 0l0 -4",
            "key": "svg-2"
        }
    ]
];
const IconDeviceFloppy = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"])("outline", "device-floppy", "DeviceFloppy", __iconNode);
;
 //# sourceMappingURL=IconDeviceFloppy.mjs.map
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconDeviceFloppy.mjs [app-ssr] (ecmascript) <export default as IconDeviceFloppy>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "IconDeviceFloppy",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconDeviceFloppy$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconDeviceFloppy$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconDeviceFloppy.mjs [app-ssr] (ecmascript)");
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconPlus.mjs [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * @license @tabler/icons-react v3.35.0 - MIT
 *
 * This source code is licensed under the MIT license.
 * See the LICENSE file in the root directory of this source tree.
 */ __turbopack_context__.s([
    "__iconNode",
    ()=>__iconNode,
    "default",
    ()=>IconPlus
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/createReactComponent.mjs [app-ssr] (ecmascript)");
;
const __iconNode = [
    [
        "path",
        {
            "d": "M12 5l0 14",
            "key": "svg-0"
        }
    ],
    [
        "path",
        {
            "d": "M5 12l14 0",
            "key": "svg-1"
        }
    ]
];
const IconPlus = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"])("outline", "plus", "Plus", __iconNode);
;
 //# sourceMappingURL=IconPlus.mjs.map
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconPlus.mjs [app-ssr] (ecmascript) <export default as IconPlus>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "IconPlus",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconPlus$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconPlus$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconPlus.mjs [app-ssr] (ecmascript)");
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconRefresh.mjs [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * @license @tabler/icons-react v3.35.0 - MIT
 *
 * This source code is licensed under the MIT license.
 * See the LICENSE file in the root directory of this source tree.
 */ __turbopack_context__.s([
    "__iconNode",
    ()=>__iconNode,
    "default",
    ()=>IconRefresh
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/createReactComponent.mjs [app-ssr] (ecmascript)");
;
const __iconNode = [
    [
        "path",
        {
            "d": "M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4",
            "key": "svg-0"
        }
    ],
    [
        "path",
        {
            "d": "M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4",
            "key": "svg-1"
        }
    ]
];
const IconRefresh = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"])("outline", "refresh", "Refresh", __iconNode);
;
 //# sourceMappingURL=IconRefresh.mjs.map
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconRefresh.mjs [app-ssr] (ecmascript) <export default as IconRefresh>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "IconRefresh",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconRefresh$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconRefresh$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconRefresh.mjs [app-ssr] (ecmascript)");
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconTrash.mjs [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * @license @tabler/icons-react v3.35.0 - MIT
 *
 * This source code is licensed under the MIT license.
 * See the LICENSE file in the root directory of this source tree.
 */ __turbopack_context__.s([
    "__iconNode",
    ()=>__iconNode,
    "default",
    ()=>IconTrash
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/createReactComponent.mjs [app-ssr] (ecmascript)");
;
const __iconNode = [
    [
        "path",
        {
            "d": "M4 7l16 0",
            "key": "svg-0"
        }
    ],
    [
        "path",
        {
            "d": "M10 11l0 6",
            "key": "svg-1"
        }
    ],
    [
        "path",
        {
            "d": "M14 11l0 6",
            "key": "svg-2"
        }
    ],
    [
        "path",
        {
            "d": "M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12",
            "key": "svg-3"
        }
    ],
    [
        "path",
        {
            "d": "M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3",
            "key": "svg-4"
        }
    ]
];
const IconTrash = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"])("outline", "trash", "Trash", __iconNode);
;
 //# sourceMappingURL=IconTrash.mjs.map
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconTrash.mjs [app-ssr] (ecmascript) <export default as IconTrash>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "IconTrash",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconTrash$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconTrash$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconTrash.mjs [app-ssr] (ecmascript)");
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconX.mjs [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * @license @tabler/icons-react v3.35.0 - MIT
 *
 * This source code is licensed under the MIT license.
 * See the LICENSE file in the root directory of this source tree.
 */ __turbopack_context__.s([
    "__iconNode",
    ()=>__iconNode,
    "default",
    ()=>IconX
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/createReactComponent.mjs [app-ssr] (ecmascript)");
;
const __iconNode = [
    [
        "path",
        {
            "d": "M18 6l-12 12",
            "key": "svg-0"
        }
    ],
    [
        "path",
        {
            "d": "M6 6l12 12",
            "key": "svg-1"
        }
    ]
];
const IconX = (0, __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$createReactComponent$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"])("outline", "x", "X", __iconNode);
;
 //# sourceMappingURL=IconX.mjs.map
}),
"[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconX.mjs [app-ssr] (ecmascript) <export default as IconX>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "IconX",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconX$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$tailwind$2f$node_modules$2f2e$pnpm$2f40$tabler$2b$icons$2d$react$40$3$2e$35$2e$0_react$40$19$2e$2$2e$0$2f$node_modules$2f40$tabler$2f$icons$2d$react$2f$dist$2f$esm$2f$icons$2f$IconX$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/tailwind/node_modules/.pnpm/@tabler+icons-react@3.35.0_react@19.2.0/node_modules/@tabler/icons-react/dist/esm/icons/IconX.mjs [app-ssr] (ecmascript)");
}),
];

//# sourceMappingURL=d5f0f_%40tabler_icons-react_dist_esm_2382b51b._.js.map