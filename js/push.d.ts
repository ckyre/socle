export declare const BASE_PAR_DEFAUT: string;
export declare const SERVICE_WORKER: string;

export type Possibilite = "ok" | "installer" | "non-supporte";
export interface EtatPush {
  possible: Possibilite;
  configure: boolean | null;
  permission: NotificationPermission | null;
  abonne: boolean;
}
export interface OptionsPush {
  /** Chemin des abonnements : « /__notifications/push » (applications, par la passerelle) par défaut. */
  base?: string;
  /** Nom de l'appareil montré dans le portail. */
  label?: string;
}

export declare function pushPossible(): Possibilite;
export declare function nomAppareil(): string;
export declare function etatPush(options?: OptionsPush): Promise<EtatPush>;
export declare function activerPush(options?: OptionsPush): Promise<PushSubscription>;
export declare function desactiverPush(options?: OptionsPush): Promise<void>;
export declare function testerPush(options?: OptionsPush): Promise<number>;
export declare function synchroniserPush(options?: OptionsPush): Promise<void>;
export declare function effacerPastille(): void;

/** <socle-push base="…" titre="…"></socle-push> dans le JSX de React (18 et 19). */
type AttributsSoclePush = {
  base?: string;
  titre?: string;
  className?: string;
  id?: string;
  ref?: import("react").Ref<HTMLElement>;
};
declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "socle-push": AttributsSoclePush;
    }
  }
}
