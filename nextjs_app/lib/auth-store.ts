// PROJ-25: In-Memory-Halter für den kurzlebigen Access-Token.
// Bewusst NICHT in localStorage — der Access-Token lebt nur im Speicher der
// laufenden Seite (XSS-Persistenz-Schutz); überlebt wird der Login allein über
// den httpOnly-Refresh-Cookie (vom Backend gesetzt), aus dem `/auth/refresh`
// beim Laden einen frischen Access-Token zieht.

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}
