// Makes the exported web demo open straight from the folder (relative paths),
// then copies it to ../docs for GitHub Pages (Settings > Pages > main /docs).
const fs = require("fs"), path = require("path");
const f = "web-demo/index.html";
fs.writeFileSync(f, fs.readFileSync(f, "utf8").replace(/"\/(_expo|favicon)/g, '"./$1'));
const docs = path.join("..", "docs");
fs.rmSync(docs, { recursive: true, force: true });
fs.cpSync("web-demo", docs, { recursive: true });
fs.writeFileSync(path.join(docs, ".nojekyll"), "");   // GitHub Pages: keep the _expo folder
console.log("web-demo ready: open web-demo/index.html or run START-WEB-DEMO.bat (also copied to docs/ for GitHub Pages)");
