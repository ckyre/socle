// Greffon Vite : sert le service worker commun (socle/js/sw.js) à la racine de l'application, sous /socle-sw.js,
// en développement comme dans le build. Il suit ainsi la version du socle référencée par l'application.
//
//   // vite.config.ts
//   import socle from "socle/vite";
//   export default defineConfig({ plugins: [react(), tailwindcss(), socle()] });

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const SW_PATH = "/socle-sw.js";

export default function socle() {
  const source = () => readFileSync(fileURLToPath(new URL("./sw.js", import.meta.url)), "utf8");
  return {
    name: "socle-service-worker",
    configureServer(server) {
      server.middlewares.use(SW_PATH, (_req, res) => {
        res.setHeader("Content-Type", "text/javascript; charset=utf-8");
        res.setHeader("Cache-Control", "no-cache");
        res.end(source());
      });
    },
    generateBundle() {
      this.emitFile({ type: "asset", fileName: SW_PATH.slice(1), source: source() });
    },
  };
}
