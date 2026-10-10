// Makes the exported web demo open straight from the folder (relative paths).
const fs = require("fs");
const f = "web-demo/index.html";
fs.writeFileSync(f, fs.readFileSync(f, "utf8").replace(/"\/(_expo|favicon)/g, '"./$1'));
console.log("web-demo ready: open web-demo/index.html or run START-WEB-DEMO.bat");
