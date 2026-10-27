// Greffons Vite du socle.
//
// - socle() : sert le service worker commun (socle/js/sw.js) à la racine, sous /socle-sw.js, en développement comme
//   dans le build, et ajoute l'animation d'ouverture (ouverture(), ci-dessous).
// - ouverture() : animation d'ouverture de la suite, seule (applications qui n'utilisent pas /socle-sw.js).
//
//   // vite.config.ts
//   import socle from "socle/vite";
//   export default defineConfig({ plugins: [react(), tailwindcss(), socle()] });
//
//   import { ouverture } from "socle/vite";
//   export default defineConfig({ plugins: [react(), ouverture()] });
//
// Animation d'ouverture (cahier des charges : claude/ouverture-suite.md du projet « Suite personnelle »)
// ------------------------------------------------------------------------------------------------------
// Au build, index.html reçoit, sans aucune dépendance au JavaScript de l'application ni aux polices :
// - dans <head> : le CSS de la mise en scène commune, suivi du geste propre à l'application
//   (frontend/ouverture.css), et un petit script synchrone ;
// - en tête de <body> : un calque plein écran, au fond de l'application (background_color du manifest), avec
//   l'icône (public/favicon.svg) en ligne.
// Le script ne joue l'animation qu'au démarrage à froid de l'onglet (sessionStorage ; « ?ouverture » dans l'adresse
// la force, pour les essais), réduit tout à un fondu si le système demande moins d'animations, et ouvre
// l'application dès que React a rempli #root, mais pas avant 0,95 s : le geste finit à 0,75 s et l'icône reste
// 0,2 s au repos pour qu'on le voie en entier. Délai de secours : 8 s.

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export const SW_PATH = "/socle-sw.js";

/** Durée de référence du cycle : les pourcentages des gestes (ouverture.css) s'y rapportent. */
export const CYCLE_OUVERTURE = "2.2s";

/** Délai minimal avant l'ouverture (ms) : fin du geste (0,75 s) plus 0,2 s de pause, l'icône au repos. */
export const DELAI_OUVERTURE = 950;

const COURBE = "cubic-bezier(.4,0,.2,1)";

function cssCommun(fond) {
  return `#socle-ouverture{display:none}
.so-oui #socle-ouverture{display:flex;position:fixed;top:0;right:0;bottom:0;left:0;z-index:2147483647;align-items:center;justify-content:center;background:${fond};transition:opacity .25s ${COURBE}}
#socle-ouverture .so-ic{width:112px;height:112px;transition:transform .2s ${COURBE}}
#socle-ouverture .so-ic>svg{display:block;width:100%;height:100%;overflow:visible}
.so-oui #socle-ouverture .so-ic{animation:so-eclo .47s ${COURBE} .13s both}
#socle-ouverture [class^="o-"]{transform-box:view-box;animation-duration:${CYCLE_OUVERTURE};animation-fill-mode:both;animation-timing-function:${COURBE};animation-iteration-count:1}
@keyframes so-eclo{0%{transform:scale(1)}36%{transform:scale(.92)}72%{transform:scale(1.04)}100%{transform:scale(1)}}
.so-ouvre #socle-ouverture{opacity:0;pointer-events:none}
.so-ouvre #socle-ouverture .so-ic{animation:none;transform:scale(1.18)}
.so-reduit #socle-ouverture .so-ic,.so-reduit #socle-ouverture [class^="o-"]{animation:none!important}
.so-reduit.so-ouvre #socle-ouverture .so-ic{transform:none}
`;
}

function scriptCommun(racine) {
  return `(function(){var d=document.documentElement,K="socle-ouverture",R=${JSON.stringify(racine)};
try{if(!/[?&]ouverture\\b/.test(location.search)){if(sessionStorage.getItem(K))return;}sessionStorage.setItem(K,"1");}catch(e){}
d.classList.add("so-oui");
try{if(matchMedia("(prefers-reduced-motion: reduce)").matches)d.classList.add("so-reduit");}catch(e){}
var t0=Date.now(),fini=false;
function ouvrir(){if(fini)return;fini=true;var reste=d.classList.contains("so-reduit")?0:Math.max(0,${DELAI_OUVERTURE}-(Date.now()-t0));
setTimeout(function(){d.classList.add("so-ouvre");setTimeout(function(){var e=document.getElementById(K);if(e&&e.parentNode)e.parentNode.removeChild(e);d.classList.remove("so-oui","so-ouvre","so-reduit");},320);},reste);}
function guetter(){var r=document.getElementById(R);if(!r||r.firstElementChild){ouvrir();return;}
new MutationObserver(function(m,o){if(r.firstElementChild){o.disconnect();requestAnimationFrame(function(){requestAnimationFrame(ouvrir);});}}).observe(r,{childList:true});}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",guetter);else guetter();
setTimeout(ouvrir,8000);})();
`;
}

function lire(chemin) {
  try {
    return readFileSync(chemin, "utf8");
  } catch {
    return null;
  }
}

function fondDuManifest(dossierPublic) {
  for (const nom of ["manifest.webmanifest", "manifest.json"]) {
    const texte = lire(join(dossierPublic, nom));
    if (!texte) continue;
    try {
      const fond = JSON.parse(texte).background_color;
      if (fond) return fond;
    } catch {
      /* manifest illisible : fond par défaut */
    }
  }
  return null;
}

/** L'icône en ligne : sans prologue XML ni commentaires, sans largeur ni hauteur (le CSS la met à 112 px). */
function svgEnLigne(svg) {
  return svg
    .replace(/<\?xml[^>]*>\s*/g, "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<svg\b([^>]*)>/, (_, attrs) => `<svg${attrs.replace(/\s(width|height)="[^"]*"/g, "")} aria-hidden="true" focusable="false">`)
    .trim();
}

const empreinte = (texte) => createHash("sha256").update(texte).digest("hex").slice(0, 10);

/**
 * Animation d'ouverture.
 * @param {{ fond?: string, css?: string, racine?: string, externe?: boolean, actif?: boolean }} [options]
 *   fond : couleur du calque (défaut : background_color du manifest) ; css : chemin du geste (défaut :
 *   <racine Vite>/ouverture.css) ; racine : id de l'élément où React s'affiche (défaut : "root") ; externe : CSS et
 *   script dans deux fichiers au lieu d'être en ligne (page servie avec une CSP sans 'unsafe-inline', comme le
 *   portail) ; actif : false pour désactiver.
 */
export function ouverture(options = {}) {
  let racineVite = process.cwd();
  let dossierPublic = join(racineVite, "public");

  function contenu() {
    const svg = lire(join(dossierPublic, "favicon.svg"));
    if (!svg) return null;
    const fond = options.fond || fondDuManifest(dossierPublic) || "#FFFFFF";
    // Le geste, sans ses commentaires (ils restent dans ouverture.css).
    const geste = (lire(options.css || join(racineVite, "ouverture.css")) || "").replace(/\/\*[\s\S]*?\*\//g, "").trim();
    return {
      css: cssCommun(fond) + geste,
      js: scriptCommun(options.racine || "root"),
      svg: svgEnLigne(svg),
    };
  }

  return {
    name: "socle-ouverture",
    configResolved(config) {
      racineVite = config.root;
      if (config.publicDir) dossierPublic = config.publicDir;
    },
    configureServer(server) {
      if (!options.externe) return;
      server.middlewares.use((req, res, next) => {
        const chemin = (req.url || "").split("?")[0];
        const c = chemin === "/socle-ouverture.css" || chemin === "/socle-ouverture.js" ? contenu() : null;
        if (!c) return next();
        const css = chemin.endsWith(".css");
        res.setHeader("Content-Type", css ? "text/css; charset=utf-8" : "text/javascript; charset=utf-8");
        res.setHeader("Cache-Control", "no-cache");
        res.end(css ? c.css : c.js);
      });
    },
    generateBundle() {
      if (!options.externe || options.actif === false) return;
      const c = contenu();
      if (!c) return;
      this.emitFile({ type: "asset", fileName: "socle-ouverture.css", source: c.css });
      this.emitFile({ type: "asset", fileName: "socle-ouverture.js", source: c.js });
    },
    transformIndexHtml() {
      if (options.actif === false) return [];
      const c = contenu();
      if (!c) return [];
      const tete = options.externe
        ? [
            { tag: "link", attrs: { rel: "stylesheet", href: `/socle-ouverture.css?v=${empreinte(c.css)}` }, injectTo: "head-prepend" },
            { tag: "script", attrs: { src: `/socle-ouverture.js?v=${empreinte(c.js)}` }, injectTo: "head-prepend" },
          ]
        : [
            { tag: "style", attrs: { id: "socle-ouverture-css" }, children: c.css, injectTo: "head-prepend" },
            { tag: "script", children: c.js, injectTo: "head-prepend" },
          ];
      return [
        ...tete,
        {
          tag: "div",
          attrs: { id: "socle-ouverture", "aria-hidden": "true" },
          children: `<div class="so-ic">${c.svg}</div>`,
          injectTo: "body-prepend",
        },
      ];
    },
  };
}

function serviceWorker() {
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

/**
 * Service worker commun (/socle-sw.js) et animation d'ouverture.
 * @param {{ ouverture?: Parameters<typeof ouverture>[0] | false }} [options]
 */
export default function socle(options = {}) {
  const plugins = [serviceWorker()];
  if (options.ouverture !== false) plugins.push(ouverture(options.ouverture || {}));
  return plugins;
}
