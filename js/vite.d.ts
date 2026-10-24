import type { Plugin } from "vite";

export declare const SW_PATH: string;
/** Sert le service worker commun à la racine (/socle-sw.js), en développement et dans le build. */
export default function socle(): Plugin;
