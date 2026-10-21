// Vérifie le kit CSS du socle et construit la page d'exemple.
//
//   npm install --no-save tailwindcss@4.3.3 @tailwindcss/node@4.3.3
//   node scripts/verifier-css.mjs
//
// 1. Compile exemples/exemple.css (Tailwind 4 + tout le socle + thèmes des applications) : toute erreur échoue.
// 2. Vérifie que chaque var(--…) employée par le socle est définie (faute de frappe dans un jeton).
// 3. Vérifie l'ordre des couches et la présence des composants, utilitaires et jetons attendus.
// 4. Écrit exemples/dist/index.html, page autonome (CSS intégré) à ouvrir dans un navigateur.

import { compile, optimize } from "@tailwindcss/node";
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const racine = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dossierCss = join(racine, "css");
const dossierExemple = join(racine, "exemples");
const erreurs = [];
const verifier = (condition, message) => condition || erreurs.push(message);

// --- 1. Compilation -----------------------------------------------------------
const html = readFileSync(join(dossierExemple, "index.html"), "utf8");
const candidats = new Set();
for (const [, classes] of html.matchAll(/class="([^"]+)"/g)) classes.split(/\s+/).forEach((c) => c && candidats.add(c));
// Utilitaires créés par les jetons, à vérifier même si la page ne les emploie pas.
const attendus = ["bg-accent-soft", "text-muted", "border-line", "rounded-card", "p-gutter", "min-h-tap", "h-control", "max-w-app", "font-display", "text-caption", "shadow-float", "stack", "row", "spread", "cluster", "fill", "divided"];
attendus.forEach((c) => candidats.add(c));

const source = readFileSync(join(dossierExemple, "exemple.css"), "utf8");
const compilateur = await compile(source, { base: dossierExemple, onDependency: () => {} });
const brut = compilateur.build([...candidats]);
const css = optimize(brut, { minify: true }).code;

// --- 2. Variables employées mais jamais définies --------------------------------
const definies = new Set([...brut.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
for (const fichier of readdirSync(dossierCss).filter((f) => f.endsWith(".css"))) {
  const texte = readFileSync(join(dossierCss, fichier), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  for (const [, nom, repli] of texte.matchAll(/var\((--[\w-]+)\s*(,)?/g)) {
    verifier(definies.has(nom) || repli, `${fichier} : var(${nom}) n'est définie nulle part`);
  }
}

// --- 3. Contenu attendu ---------------------------------------------------------
// Les composants restent sous les utilitaires : « btn w-full » donne bien une largeur de 100 %.
const ordre = [...new Set([...css.matchAll(/@layer ([a-z]+)[;{,]/g)].map((m) => m[1]))].filter((c) => c !== "properties");
verifier(ordre.join(",") === "theme,base,components,utilities", `ordre des couches inattendu : ${ordre}`);
const selecteurs = [".app", ".screen", ".nav", ".nav-floating", ".sheet", ".sheet-backdrop", ".toast", ".fab", ".action-bar", ".topbar",
  ".btn", ".btn-primary", ".icon-btn", ".link-btn", ".input", ".switch", ".chip", ".segmented", ".pill", ".card", ".list-row", ".empty",
  ".banner", ".sr-only", ".bg-accent-soft", ".rounded-card", ".p-gutter", ".max-w-app", ".stack", ".fill"];
for (const s of selecteurs) verifier(new RegExp(`${s.replace(/[.\\]/g, "\\$&")}[{,:\\s.>\\[]`).test(css), `sélecteur absent : ${s}`);
for (const jeton of ["--color-accent", "--color-accent-soft", "--color-muted", "--font-display", "--radius-control", "--container-app", "--socle-bottom-offset"]) {
  verifier(definies.has(jeton), `jeton absent : ${jeton}`);
}

// --- 4. Page d'exemple autonome ---------------------------------------------------
mkdirSync(join(dossierExemple, "dist"), { recursive: true });
const page = html.replace(/<link rel="stylesheet" href="\.\/exemple\.css" \/>/, () => `<style>${css}</style>`);
writeFileSync(join(dossierExemple, "dist", "index.html"), page);

if (erreurs.length) {
  console.error(erreurs.map((e) => `✗ ${e}`).join("\n"));
  process.exit(1);
}
console.log(`✓ CSS du socle vérifié (${(css.length / 1024).toFixed(1)} Ko minifié pour la page d'exemple) → exemples/dist/index.html`);
