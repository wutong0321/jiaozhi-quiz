const fs = require("fs");
let h = fs.readFileSync("index.html", "utf8");
h = h.replace(/^\s*<!--\s*AI生成\s*-->\s*\n/, "");
// remove the watermark paragraph if still present
h = h.replace(/<p\s+data-aigc-mark="1"[^>]*>\s*AI生成\s*<\/p>\s*\n?/g, "");
if (!h.includes("[data-aigc-mark]")) {
  h = h.replace("</style>", "  [data-aigc-mark], .aigc-mark { display: none !important; }\n</style>");
}
// ensure strip script exists
if (!h.includes("data-aigc-mark") || !h.includes("wipe")) {
  // already handled by edit tool usually
}
fs.writeFileSync("index.html", h);
const h2 = fs.readFileSync("index.html", "utf8");
console.log("has visible p", h2.includes('data-aigc-mark="1"'));
console.log("has comment", h2.includes("<!-- AI生成 -->"));
console.log("has header", h2.includes("EXAM PRACTICE"));
console.log("has hide css", h2.includes("[data-aigc-mark]"));
console.log("has wipe js", h2.includes("wipe") || h2.includes("MutationObserver"));
fs.copyFileSync("index.html", "android/app/src/main/assets/www/index.html");
console.log("copied to android www");
