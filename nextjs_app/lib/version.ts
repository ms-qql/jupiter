// PROJ-8: zentrale App-Version. Quelle = package.json, zur Build-Zeit über
// next.config.ts als NEXT_PUBLIC_APP_VERSION injiziert (nicht manuell gepflegt).

export const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "0.0.0";
