// Icônes d'écran d'accueil (iOS et Android) des applications de la suite, tirées de leur favicon.svg.
//
// Usage, depuis le dossier qui contient tous les dépôts (ex. E:\dev) :
//
//     npm install --prefix socle --no-save @resvg/resvg-js   (une fois)
//     node socle/scripts/icones.mjs                          (toutes les applications)
//     node socle/scripts/icones.mjs mijote vigie             (seulement celles-ci)
//
// Pour chaque application (dossier qui contient frontend/public/favicon.svg) :
// - crée dans frontend/public/ :
//     apple-touch-icon.png    180×180 : iOS (« Sur l'écran d'accueil »), qui n'accepte pas le SVG ;
//     icone-192.png, icone-512.png    : Android et Chrome (manifest, « any ») ;
//     icone-maskable-512.png          : Android, pictogramme réduit pour tenir dans le masque (cercle, goutte…) ;
//   tous à fond plein et sans coins arrondis : le système applique lui-même sa forme ;
// - ajoute ces icônes au manifest.webmanifest (le crée s'il manque) ;
// - ajoute à index.html les balises apple-touch-icon, manifest, apple-mobile-web-app-title et theme-color.
//
// Le script est idempotent : le relancer après un changement de logo met les fichiers à jour sans rien dupliquer.
// Rien n'est commité : vérifiez le résultat, puis commitez dans chaque dépôt.
//
// La passerelle du portail laisse passer ces fichiers sans session (PUBLIC_PATHS de gateway/entrypoint.sh) :
// Android télécharge le manifest et ses icônes sans cookie.

import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
let Resvg;
try {
  ({ Resvg } = require("@resvg/resvg-js"));
} catch {
  console.error("Il manque @resvg/resvg-js : npm install --prefix socle --no-save @resvg/resvg-js");
  process.exit(2);
}

// Pictogramme dans le masque Android : zone sûre = cercle de 80 % du côté. Le pictogramme des favicons occupe
// 36/64 du côté ; réduit à 80 %, sa diagonale tient dans ce cercle.
const ECHELLE_MASKABLE = 0.8;

export const FICHIERS = [
  { nom: "apple-touch-icon.png", taille: 180 },
  { nom: "icone-192.png", taille: 192 },
  { nom: "icone-512.png", taille: 512 },
  { nom: "icone-maskable-512.png", taille: 512, echelle: ECHELLE_MASKABLE },
];

/** Décompose un favicon de la suite : fond (premier <rect>) et pictogramme (le reste). */
export function decomposer(svg) {
  const propre = svg.replace(/<metadata>[\s\S]*?<\/metadata>/g, "").replace(/<!--[\s\S]*?-->/g, "");
  const ouverture = propre.match(/<svg\b[^>]*>/);
  if (!ouverture) throw new Error("pas de balise <svg>");
  const viewBox = ouverture[0].match(/viewBox="([^"]+)"/)?.[1] ?? "0 0 64 64";
  const [, , largeur, hauteur] = viewBox.split(/[\s,]+/).map(Number);
  const corps = propre.slice(propre.indexOf(ouverture[0]) + ouverture[0].length, propre.lastIndexOf("</svg>"));
  const fond = corps.match(/^\s*<rect\b[^>]*\bfill="([^"]+)"[^>]*\/>/);
  if (!fond) throw new Error("le favicon doit commencer par un <rect> de fond (fill=…)");
  return { largeur, hauteur, couleur: fond[1], pictogramme: corps.slice(fond[0].length).trim() };
}

/** SVG carré, fond plein sans arrondi, pictogramme éventuellement réduit autour du centre. */
export function composer({ largeur, hauteur, couleur, pictogramme }, echelle = 1) {
  const cx = largeur / 2;
  const cy = hauteur / 2;
  const contenu =
    echelle === 1 ? pictogramme : `<g transform="translate(${cx} ${cy}) scale(${echelle}) translate(${-cx} ${-cy})">${pictogramme}</g>`;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${largeur} ${hauteur}">` +
    `<rect width="${largeur}" height="${hauteur}" fill="${couleur}"/>${contenu}</svg>`
  );
}

export function png(svg, taille) {
  return new Resvg(svg, { fitTo: { mode: "width", value: taille } }).render().asPng();
}

/** Icônes du manifest : SVG (navigateurs de bureau) puis PNG (Android). */
export function iconesManifest() {
  return [
    { src: "/favicon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    { src: "/icone-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
    { src: "/icone-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    { src: "/icone-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ];
}

function titre(html, nomDossier) {
  const t = html.match(/<title>([^<]*)<\/title>/)?.[1]?.trim();
  return t || nomDossier;
}

function themeColor(html) {
  return html.match(/<meta\s+name="theme-color"\s+content="([^"]+)"/)?.[1];
}

export function majManifest(texte, { nom, couleurTheme }) {
  const m = texte ? JSON.parse(texte) : {};
  // Ordre des clés existantes conservé ; seules les clés manquantes sont ajoutées.
  const defauts = { name: nom, short_name: nom, lang: "fr", start_url: "/", display: "standalone" };
  if (couleurTheme) Object.assign(defauts, { background_color: couleurTheme, theme_color: couleurTheme });
  const resultat = { ...defauts, ...m };
  for (const k of Object.keys(m)) delete resultat[k];
  return formater({ ...m, ...resultat, icons: iconesManifest() });
}

/** JSON lisible et compact : une clé par ligne, un objet imbriqué ou un élément de liste par ligne. */
function formater(objet) {
  const valeur = (v) => {
    if (Array.isArray(v)) return v.length ? `[\n${v.map((x) => `    ${JSON.stringify(x, null, 1).replace(/\n\s*/g, " ")}`).join(",\n")}\n  ]` : "[]";
    return JSON.stringify(v, null, 1).replace(/\n\s*/g, " ");
  };
  const lignes = Object.entries(objet).map(([k, v]) => `  ${JSON.stringify(k)}: ${valeur(v)}`);
  return `{\n${lignes.join(",\n")}\n}\n`;
}

/** Ajoute les balises manquantes juste après le lien vers le favicon (ou avant </head>). */
export function majIndex(html, { nom, couleurTheme }) {
  const balises = [];
  if (!/rel="apple-touch-icon"/.test(html)) balises.push('<link rel="apple-touch-icon" href="/apple-touch-icon.png" />');
  if (!/rel="manifest"/.test(html)) balises.push('<link rel="manifest" href="/manifest.webmanifest" />');
  if (!/name="apple-mobile-web-app-title"/.test(html))
    balises.push(`<meta name="apple-mobile-web-app-title" content="${nom}" />`);
  if (couleurTheme && !/name="theme-color"/.test(html))
    balises.push(`<meta name="theme-color" content="${couleurTheme}" />`);
  if (!balises.length) return html;

  const favicon = html.match(/^([ \t]*)<link\b[^>]*rel="icon"[^>]*>\n/m);
  if (favicon) {
    const indent = favicon[1];
    const ajout = balises.map((b) => indent + b + "\n").join("");
    const fin = favicon.index + favicon[0].length;
    return html.slice(0, fin) + ajout + html.slice(fin);
  }
  const head = html.match(/^([ \t]*)<\/head>/m);
  if (!head) throw new Error("index.html sans </head>");
  const indent = head[1] + "  ";
  return html.slice(0, head.index) + balises.map((b) => indent + b + "\n").join("") + html.slice(head.index);
}

/** Lit un fichier texte en LF ; l'écriture rétablit ses fins de ligne (CRLF sous Windows). */
function lire(chemin) {
  const brut = readFileSync(chemin, "utf8");
  return { texte: brut.replace(/\r\n/g, "\n"), crlf: brut.includes("\r\n") };
}

function ecrire(chemin, texte, crlf) {
  writeFileSync(chemin, crlf ? texte.replace(/\n/g, "\r\n") : texte);
}

function traiter(racine, nomDossier, couleursTheme) {
  const front = join(racine, nomDossier, "frontend");
  const pub = join(front, "public");
  const svg = readFileSync(join(pub, "favicon.svg"), "utf8");
  const parties = decomposer(svg);
  for (const f of FICHIERS) writeFileSync(join(pub, f.nom), png(composer(parties, f.echelle ?? 1), f.taille));

  const cheminIndex = join(front, "index.html");
  const { texte: html, crlf: crlfIndex } = lire(cheminIndex);
  const nom = titre(html, nomDossier);
  const couleurTheme = themeColor(html) ?? couleursTheme[nomDossier];

  const cheminManifest = join(pub, "manifest.webmanifest");
  const ancien = existsSync(cheminManifest) ? lire(cheminManifest) : { texte: "", crlf: crlfIndex };
  ecrire(cheminManifest, majManifest(ancien.texte, { nom, couleurTheme }), ancien.crlf);
  ecrire(cheminIndex, majIndex(html, { nom, couleurTheme }), crlfIndex);
  console.log(`${nomDossier} : ${FICHIERS.map((f) => f.nom).join(", ")}, manifest, index.html`);
}

function main() {
  const racine = resolve(process.cwd());
  // theme-color des applications dont index.html n'en déclare pas (= --color-ground de leur CSS).
  const couleursTheme = { charge: "#08090a", fund: "#0c0e10", portail: "#eef0f3" };
  const demandees = process.argv.slice(2);
  const applis = (demandees.length ? demandees : readdirSync(racine)).filter((d) =>
    existsSync(join(racine, d, "frontend", "public", "favicon.svg")),
  );
  if (!applis.length) {
    console.error("Aucune application trouvée (dossier/frontend/public/favicon.svg) : lancez depuis E:\\dev.");
    process.exit(1);
  }
  let erreurs = 0;
  for (const a of applis) {
    try {
      traiter(racine, a, couleursTheme);
    } catch (e) {
      erreurs++;
      console.error(`${a} : ${e.message}`);
    }
  }
  process.exit(erreurs ? 1 : 0);
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith("icones.mjs")) main();
