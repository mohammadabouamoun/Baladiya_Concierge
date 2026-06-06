import { readdirSync, statSync } from "fs";
import { join } from "path";
import { gzipSync } from "zlib";
import { readFileSync } from "fs";

const distDir = join(process.cwd(), "dist", "assets");
const MAX_GZIP_KB = 100;

let totalGzip = 0;
for (const file of readdirSync(distDir)) {
  if (file.endsWith(".js")) {
    const content = readFileSync(join(distDir, file));
    const gzipped = gzipSync(content);
    totalGzip += gzipped.byteLength;
    console.log(`  ${file}: ${(gzipped.byteLength / 1024).toFixed(1)} KB gzipped`);
  }
}

const totalKB = totalGzip / 1024;
console.log(`\nTotal JS gzipped: ${totalKB.toFixed(1)} KB (limit: ${MAX_GZIP_KB} KB)`);

if (totalKB > MAX_GZIP_KB) {
  console.error(`FAIL: bundle exceeds ${MAX_GZIP_KB} KB gzipped`);
  process.exit(1);
}
console.log("PASS: bundle within size limit");
