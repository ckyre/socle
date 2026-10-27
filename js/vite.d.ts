import type { Plugin } from "vite";

export declare const SW_PATH: string;
/** Durée de référence du cycle d'ouverture : les pourcentages des gestes (ouverture.css) s'y rapportent. */
export declare const CYCLE_OUVERTURE: string;

export interface OptionsOuverture {
  /** Couleur du calque d'ouverture. Défaut : background_color du manifest de public/. */
  fond?: string;
  /** Chemin du CSS du geste. Défaut : <racine Vite>/ouverture.css. */
  css?: string;
  /** id de l'élément où React s'affiche. Défaut : "root". */
  racine?: string;
  /** CSS et script dans deux fichiers au lieu d'être en ligne (CSP sans 'unsafe-inline', comme le portail). */
  externe?: boolean;
  /** false : pas d'animation d'ouverture. */
  actif?: boolean;
}

/** Animation d'ouverture de la suite, injectée dans index.html (icône public/favicon.svg, geste ouverture.css). */
export declare function ouverture(options?: OptionsOuverture): Plugin;

/** Sert le service worker commun à la racine (/socle-sw.js), en développement et dans le build, et ajoute
 * l'animation d'ouverture (sauf `{ ouverture: false }`). */
export default function socle(options?: { ouverture?: OptionsOuverture | false }): Plugin[];
