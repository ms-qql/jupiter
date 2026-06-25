"""ChallengeService — Cross-Agent-Review / Challenge (PROJ-23).

Lässt das **Ergebnis eines Agenten von einem anderen Agenten herausfordern** —
bevorzugt mit anderer Engine/anderem Modell. Eine Challenge auf einem Artefakt
(Architektur-Doku/ADR oder Diff/Code, referenziert als **Vault-Pointer**) startet eine
kurze **Reviewer-Session** über das bestehende Treiber-Modell (PROJ-1/PROJ-22). Der
Reviewer prüft adversariell und liefert **strukturierte Befunde** (Schweregrad +
Fundstelle + Gegenvorschlag); sie erscheinen als nicht-blockierende
``card_type="review_finding"``-Cards (PROJ-4-Mechanik) auf der Reviewer-Session und
werden als Audit-Spur in den **Vault** geschrieben (PROJ-2, ``Knowledge/``).

Kein neues Persistenz-Schema (konsistent mit PROJ-22): der Review = die Reviewer-
``SessionRuntime`` + ein In-memory-``Review``-Objekt; Wahrheit/Recovery laufen über den
Vault. Der Reviewer **ändert das Artefakt nie** (Trennung Finden/Umsetzen, analog QA):
„Übernehmen"/„Mit Kommentar zurück" reichen den Befund an die **Autor-Session** zurück
(menschliche Freigabe dort über deren eigenen Decision-Card-Flow).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from ..config import settings
from .decisions import OPEN, RESOLVED, PendingDecision
from .manager import SessionManager, SessionRuntime
from .registry import engine_registry
from .vault import VaultService

# Rundenlimit gegen Endlos-Challenge (Autor ↔ Reviewer): nach 2 Runden je Autor-Session
# wird nicht weiter automatisch gechallengt, sondern an den Menschen eskaliert (PROJ-23,
# Design-Entscheid 2026-06-25).
MAX_ROUNDS = 2

# 3-stufige Schweregrad-Skala (Design-Entscheid 2026-06-25).
VALID_SEVERITIES: frozenset[str] = frozenset({"hoch", "mittel", "niedrig"})
DEFAULT_SEVERITY = "mittel"

# Wie viel Artefakt-Inhalt maximal in den Reviewer-Prompt geht; größere Artefakte
# werden auf ein relevantes Fenster gekürzt (Pointer/RAG-Linie #23) statt stumm
# abgeschnitten.
MAX_ARTIFACT_CHARS = 24_000

CARD_TYPE = "review_finding"

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class ChallengeError(Exception):
    """Basis für fachliche Challenge-Fehler (Route übersetzt in HTTP-Status)."""


class AuthorSessionNotFoundError(ChallengeError):
    """Die zu challengende Autor-Session existiert nicht."""


class ReviewNotFoundError(ChallengeError):
    """Kein Review unter dieser ID (= Reviewer-Session-ID)."""


class FindingNotFoundError(ChallengeError):
    """Kein offener Befund unter dieser ID in diesem Review."""


class RoundLimitError(ChallengeError):
    """Rundenlimit erreicht → an den Menschen eskalieren (kein Auto-Challenge mehr)."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass
class Finding:
    """Ein einzelner Review-Befund (= eine ``review_finding``-Card auf der Reviewer-Session)."""

    finding_id: str
    severity: str
    location: str
    title: str
    suggestion: str
    state: str = OPEN              # open | resolved
    resolution: str | None = None  # übernehmen | verwerfen | zurück

    def to_read(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity,
            "location": self.location,
            "title": self.title,
            "suggestion": self.suggestion,
            "state": self.state,
            "resolution": self.resolution,
        }


@dataclass
class Review:
    """Eine Challenge: Reviewer-Session + Metadaten (Autor/Reviewer-Engine, Artefakt, Runde)."""

    review_id: str            # = Reviewer-Session-ID (1 Challenge = 1 Reviewer-Session)
    author_session_id: str
    author_engine: str
    author_model: str
    reviewer_engine: str
    reviewer_model: str
    same_engine: bool         # True = keine andere Engine verfügbar → eingeschränkte Diversität
    artifact_pointer: str
    artifact_version: str | None
    round: int
    focus: str | None = None
    collected: bool = False    # Befunde aus dem Reviewer-Output bereits materialisiert?
    incomplete: bool = False   # Reviewer-Session gestorben/Timeout → „Review unvollständig"
    findings: list[Finding] = field(default_factory=list)
    created_at: str = ""

    def to_read(self, *, stale: bool) -> dict:
        return {
            "review_id": self.review_id,
            "author_session_id": self.author_session_id,
            "author_engine": self.author_engine,
            "author_model": self.author_model,
            "reviewer_engine": self.reviewer_engine,
            "reviewer_model": self.reviewer_model,
            "same_engine": self.same_engine,
            "artifact_pointer": self.artifact_pointer,
            "artifact_version": self.artifact_version,
            "round": self.round,
            "focus": self.focus,
            "collected": self.collected,
            "incomplete": self.incomplete,
            "stale": stale,
            "created_at": self.created_at,
            "findings": [f.to_read() for f in self.findings],
        }


class ChallengeService:
    """Startet/aggregiert Cross-Agent-Reviews über dem bestehenden SessionManager."""

    def __init__(self, manager: SessionManager, vault: VaultService) -> None:
        self._manager = manager
        self._vault = vault
        self._reviews: dict[str, Review] = {}      # review_id (= reviewer session) → Review
        self._rounds: dict[str, int] = {}          # author_session_id → bisherige Runden

    # --- Engine-Auswahl ----------------------------------------------------

    def pick_reviewer_engine(self, author_engine: str, requested: str | None) -> tuple[str, bool]:
        """Reviewer-Engine wählen. ``(engine_key, same_engine)``.

        Default: eine **andere** verfügbare Session-Engine als der Autor (echte
        Diversität). Explizit gewünschte Engine gewinnt, sofern verfügbar. Gibt es keine
        andere → dieselbe Engine mit ``same_engine=True`` (Warnhinweis, statt zu blocken).
        """
        if requested:
            prof = engine_registry.get(requested)
            if prof is None or not prof.is_session_engine:
                raise ChallengeError(f"Engine '{requested}' ist keine steuerbare Session-Engine.")
            ok, reason = prof.availability()
            if not ok:
                raise ChallengeError(reason or f"Engine '{requested}' nicht verfügbar.")
            return prof.key, prof.key == author_engine
        # Erste verfügbare Session-Engine, die NICHT die Autor-Engine ist.
        for prof in engine_registry.all():
            if not prof.is_session_engine or prof.key == author_engine:
                continue
            ok, _ = prof.availability()
            if ok:
                return prof.key, False
        # Keine andere verfügbar → gleiche Engine (eingeschränkte Diversität).
        return author_engine, True

    # --- Challenge starten -------------------------------------------------

    async def start(
        self,
        author_session_id: str,
        *,
        artifact_pointer: str,
        reviewer_engine: str | None = None,
        focus: str | None = None,
    ) -> dict:
        author = self._manager.get(author_session_id)
        if author is None:
            raise AuthorSessionNotFoundError("Autor-Session nicht gefunden.")

        prev = self._rounds.get(author_session_id, 0)
        if prev >= MAX_ROUNDS:
            raise RoundLimitError(
                f"Challenge-Rundenlimit ({MAX_ROUNDS}) für diese Autor-Session erreicht — "
                "bitte als Mensch entscheiden (keine weitere automatische Challenge)."
            )
        this_round = prev + 1

        content, version = self._load_artifact(artifact_pointer, focus)
        eng_key, same = self.pick_reviewer_engine(author.state.engine, reviewer_engine)
        prompt = self._build_prompt(artifact_pointer, version, content, focus, same, author.state.engine)

        ticket = author.state.ticket_id or author.state.abc_feature
        label_base = author.state.project_name or "Artefakt"
        reviewer = await self._manager.create(
            project_path=author.state.project_path,
            initial_prompt=prompt,
            role="reviewer",
            engine=eng_key,
            project_name=f"{label_base} · Review" + (f" {ticket}" if ticket else ""),
            owner=author.state.owner,
        )
        review = Review(
            review_id=reviewer.state.session_id,
            author_session_id=author_session_id,
            author_engine=author.state.engine,
            author_model=author.state.model,
            reviewer_engine=reviewer.state.engine,
            reviewer_model=reviewer.state.model,
            same_engine=same,
            artifact_pointer=artifact_pointer,
            artifact_version=version,
            round=this_round,
            focus=focus,
            created_at=reviewer.state.created_at.isoformat(),
        )
        self._reviews[review.review_id] = review
        self._rounds[author_session_id] = this_round
        return review.to_read(stale=False)

    # --- Befunde einsammeln (lazy) -----------------------------------------

    def collect(self, review_id: str) -> Review:
        """Reviewer-Output → strukturierte Befunde + ``review_finding``-Cards + Vault-Notiz.

        Idempotent: läuft erst, wenn der Reviewer mindestens einen Turn beendet hat, und
        materialisiert die Befunde genau einmal. Stirbt/timeoutet die Reviewer-Session ohne
        verwertbaren Output, wird der Review als ``incomplete`` markiert (Retry möglich).
        """
        review = self._reviews.get(review_id)
        if review is None:
            raise ReviewNotFoundError("Review nicht gefunden.")
        if review.collected:
            return review
        runtime = self._manager.get(review_id)
        if runtime is None:
            review.incomplete = True
            return review

        status = runtime.state.status
        # Solange der Reviewer noch denkt/läuft: noch nichts einsammeln.
        if status in ("starting", "running"):
            return review

        text = self._assistant_text(runtime)
        findings = self._parse_findings(text)
        if findings is None:
            # Kein verwertbarer Output (Tod/Timeout ohne JSON) → unvollständig markieren.
            if status in ("done", "error"):
                review.incomplete = True
            return review

        review.findings = findings
        review.collected = True
        self._materialize_cards(runtime, review)
        self._write_vault_note(review)
        runtime._broadcast({"kind": "state", **runtime.to_read()})
        return review

    def _materialize_cards(self, runtime: SessionRuntime, review: Review) -> None:
        """Befunde als nicht-blockierende ``review_finding``-Cards in die Reviewer-Session hängen."""
        for f in review.findings:
            card = PendingDecision(
                decision_id=f.finding_id,
                session_id=review.review_id,
                tool_name="CrossAgentReview",
                action=f"[{f.severity}] {f.title}",
                excerpt=f.location,
                rationale=f.suggestion,
                context={
                    "review_id": review.review_id,
                    "author_session_id": review.author_session_id,
                    "author_engine": review.author_engine,
                    "author_model": review.author_model,
                    "reviewer_engine": review.reviewer_engine,
                    "reviewer_model": review.reviewer_model,
                    "same_engine": review.same_engine,
                    "artifact_pointer": review.artifact_pointer,
                    "severity": f.severity,
                },
                created_at=runtime.state.last_activity.isoformat(),
                triggering_rule=f"Cross-Agent-Review ({review.reviewer_engine}/{review.reviewer_model})",
                card_type=CARD_TYPE,
                proposal_title=f.title,
                proposal_body=f.suggestion,
            )
            runtime.pending[f.finding_id] = card  # nicht-blockierend: kein Future

    # --- Befund entscheiden ------------------------------------------------

    async def resolve_finding(
        self, review_id: str, finding_id: str, action: str, comment: str | None = None
    ) -> dict:
        """Pro Befund: ``übernehmen`` | ``verwerfen`` | ``zurück``.

        - ``übernehmen`` → Gegenvorschlag als Eingabe an die **Autor-Session** (sie setzt
          ihn über ihren eigenen Decision-Card-Flow um → menschliche Freigabe dort).
        - ``zurück`` → Befund + Nutzerkommentar an die Autor-Session (Gegenrede/Klärung).
        - ``verwerfen`` → nur schließen; das Artefakt bleibt unberührt.
        """
        review = self._reviews.get(review_id)
        if review is None:
            raise ReviewNotFoundError("Review nicht gefunden.")
        self.collect(review_id)  # idempotent: Befunde sicher materialisiert
        finding = next((f for f in review.findings if f.finding_id == finding_id), None)
        if finding is None or finding.state != OPEN:
            raise FindingNotFoundError("Befund nicht gefunden oder bereits entschieden.")
        if action not in ("übernehmen", "verwerfen", "zurück"):
            raise ChallengeError("action muss übernehmen | verwerfen | zurück sein.")

        if action in ("übernehmen", "zurück"):
            await self._route_to_author(review, finding, action, comment)

        finding.state = RESOLVED
        finding.resolution = action
        # Card auf der Reviewer-Session als entschieden entfernen + Snapshot streamen.
        runtime = self._manager.get(review_id)
        if runtime is not None:
            card = runtime.pending.get(finding_id)
            if card is not None:
                card.state = RESOLVED
                card.resolution = action
                runtime.pending.pop(finding_id, None)
                runtime._broadcast(
                    {"kind": "decision", "event": "resolved", "decision": card.to_read()}
                )
                runtime._broadcast({"kind": "state", **runtime.to_read()})
        return finding.to_read()

    async def _route_to_author(
        self, review: Review, finding: Finding, action: str, comment: str | None
    ) -> None:
        author = self._manager.get(review.author_session_id)
        if author is None:
            raise AuthorSessionNotFoundError("Autor-Session nicht mehr vorhanden.")
        if action == "übernehmen":
            text = (
                f"Cross-Agent-Review-Befund ÜBERNEHMEN (Reviewer "
                f"{review.reviewer_engine}/{review.reviewer_model}).\n"
                f"Artefakt: {review.artifact_pointer}\n"
                f"Fundstelle: {finding.location}\n"
                f"Befund [{finding.severity}]: {finding.title}\n"
                f"Gegenvorschlag: {finding.suggestion}\n"
                "Setze den Gegenvorschlag um (deine üblichen Freigaben gelten)."
            )
        else:  # zurück
            text = (
                f"Cross-Agent-Review-Befund MIT KOMMENTAR ZURÜCK (Reviewer "
                f"{review.reviewer_engine}/{review.reviewer_model}).\n"
                f"Artefakt: {review.artifact_pointer}\n"
                f"Fundstelle: {finding.location}\n"
                f"Befund [{finding.severity}]: {finding.title}\n"
                f"Gegenvorschlag des Reviewers: {finding.suggestion}\n"
                f"Kommentar des Nutzers: {(comment or '').strip() or '(kein Kommentar)'}"
            )
        try:
            await self._manager.send_input(review.author_session_id, text)
        except RuntimeError as exc:  # offene Freigabe / nicht annahmebereit
            raise ChallengeError(f"Autor-Session nimmt gerade keine Eingabe an: {exc}") from exc

    # --- Lese-Sicht --------------------------------------------------------

    def reviews_for(self, author_session_id: str) -> list[dict]:
        """Alle Reviews, in denen ``author_session_id`` die Autor-Session ist (lazy collected)."""
        out: list[dict] = []
        for review in self._reviews.values():
            if review.author_session_id != author_session_id:
                continue
            self.collect(review.review_id)  # idempotent: materialisiert fertige Befunde
            out.append(review.to_read(stale=self._is_stale(review)))
        return out

    def get_review(self, review_id: str) -> dict:
        review = self._reviews.get(review_id)
        if review is None:
            raise ReviewNotFoundError("Review nicht gefunden.")
        self.collect(review_id)
        return review.to_read(stale=self._is_stale(review))

    def _is_stale(self, review: Review) -> bool:
        """Hat sich das Artefakt seit dem Review geändert (Versions-Drift)?"""
        if review.artifact_version is None:
            return False
        try:
            data = self._vault.read_file(review.artifact_pointer.split("#", 1)[0])
        except (FileNotFoundError, ValueError, OSError):
            return False
        return _sha(data.get("content", "")) != review.artifact_version

    # --- intern ------------------------------------------------------------

    def _load_artifact(self, pointer: str, focus: str | None) -> tuple[str, str | None]:
        """Artefakt-Inhalt + Versions-Hash. Pointer ``pfad`` oder ``pfad#L10-30`` (Vault-relativ).

        Zu große Artefakte werden auf ein relevantes Fenster gekürzt (RAG, #23) statt stumm
        abgeschnitten. Nicht lesbar → leerer Inhalt + Hinweis im Prompt, Version ``None``.
        """
        rel = pointer.split("#", 1)[0]
        try:
            data = self._vault.read_file(rel)
        except (FileNotFoundError, ValueError, OSError):
            return ("(Artefakt nicht lesbar — nur der Pointer steht zur Verfügung.)", None)
        content = data.get("content", "")
        version = _sha(content)
        if len(content) <= MAX_ARTIFACT_CHARS:
            return content, version
        # Fenster um die Fokus-Begriffe (sonst um den Anfang) — kein stummes Abschneiden.
        from .vault import _best_window, _rag_terms

        terms = _rag_terms(focus or "")
        if terms:
            start, end = _best_window(content.lower(), terms, MAX_ARTIFACT_CHARS)
            snippet = content[start:end]
        else:
            snippet = content[:MAX_ARTIFACT_CHARS]
        return (
            f"(Artefakt gekürzt auf ein relevantes Fenster — {len(content)} Zeichen gesamt.)\n\n"
            + snippet
        ), version

    def _build_prompt(
        self, pointer: str, version: str | None, content: str,
        focus: str | None, same_engine: bool, author_engine: str,
    ) -> str:
        focus_line = f"Prüf-Fokus: {focus}\n" if focus else ""
        diversity = (
            "HINWEIS: Es ist nur eine Engine verfügbar — du läufst auf derselben Engine wie "
            f"der Autor ({author_engine}); die Modell-Diversität ist eingeschränkt.\n"
            if same_engine else ""
        )
        return (
            "Du bist ein adversarieller Cross-Agent-Reviewer (PROJ-23). Prüfe das folgende "
            "Artefakt unabhängig und kritisch auf Schwachstellen, Risiken, Lücken, "
            "Inkonsistenzen und Fehler. Du ÄNDERST das Artefakt NICHT — du lieferst nur "
            "Befunde.\n"
            f"{diversity}{focus_line}"
            f"Artefakt-Pointer: {pointer} (Stand-Version: {version or 'unbekannt'})\n\n"
            "--- ARTEFAKT-INHALT ---\n"
            f"{content}\n"
            "--- ENDE ARTEFAKT ---\n\n"
            "Gib deine Befunde AUSSCHLIESSLICH als ein einziges JSON-Objekt in einem "
            "```json-Codeblock aus (kein weiterer Text danach). Schema:\n"
            "```json\n"
            '{"findings": [\n'
            '  {"severity": "hoch|mittel|niedrig", "location": "Fundstelle/Bezug im '
            'Artefakt", "title": "Kurztitel", "suggestion": "konkreter Gegenvorschlag"}\n'
            "]}\n"
            "```\n"
            'Findest du keine Schwachstellen, gib {"findings": []} zurück. '
            "Alle Texte deutsch."
        )

    @staticmethod
    def _assistant_text(runtime: SessionRuntime) -> str:
        return "\n".join(
            e.text for e in runtime.transcript if e.role == "assistant" and e.kind == "text"
        )

    @classmethod
    def _parse_findings(cls, text: str) -> list[Finding] | None:
        """JSON-Block → Befundliste. ``None`` = kein verwertbarer Block; ``[]`` = keine Befunde."""
        if not text:
            return None
        matches = _JSON_BLOCK_RE.findall(text)
        payload = None
        for blob in reversed(matches):  # letzter valider Block gewinnt
            try:
                cand = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if isinstance(cand, dict) and "findings" in cand:
                payload = cand
                break
        if payload is None:
            return None
        raw = payload.get("findings")
        if not isinstance(raw, list):
            return []
        findings: list[Finding] = []
        for i, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                continue
            sev = str(item.get("severity", "")).strip().lower()
            if sev not in VALID_SEVERITIES:
                sev = DEFAULT_SEVERITY
            findings.append(
                Finding(
                    finding_id=f"finding-{i}",
                    severity=sev,
                    location=str(item.get("location", "")).strip() or "(ohne Fundstelle)",
                    title=str(item.get("title", "")).strip() or "(ohne Titel)",
                    suggestion=str(item.get("suggestion", "")).strip() or "(ohne Gegenvorschlag)",
                )
            )
        return findings

    def _write_vault_note(self, review: Review) -> None:
        """Review-Ergebnis als Audit-Spur in den Vault (``Knowledge/``) — best-effort.

        Ein Vault-Schreibfehler darf das Einsammeln der Befunde nicht verlieren lassen;
        die Befunde leben weiter als Cards + In-memory-Review.
        """
        lines = [
            f"# Cross-Agent-Review: {review.artifact_pointer}",
            "",
            f"- **Autor:** {review.author_engine} / {review.author_model}",
            f"- **Reviewer:** {review.reviewer_engine} / {review.reviewer_model}"
            + (" — ⚠️ gleiche Engine (eingeschränkte Diversität)" if review.same_engine else ""),
            f"- **Artefakt-Version:** {review.artifact_version or 'unbekannt'}",
            f"- **Runde:** {review.round}/{MAX_ROUNDS}",
            "",
        ]
        if not review.findings:
            lines.append(
                f"**Keine Befunde** — der Reviewer ({review.reviewer_engine}/"
                f"{review.reviewer_model}) hat keine Schwachstellen gemeldet."
            )
        else:
            lines.append(f"## Befunde ({len(review.findings)})")
            for f in review.findings:
                lines += [
                    "",
                    f"### [{f.severity}] {f.title}",
                    f"- **Fundstelle:** {f.location}",
                    f"- **Gegenvorschlag:** {f.suggestion}",
                ]
        body = "\n".join(lines)
        title = f"Review {review.artifact_pointer.split('/')[-1]} {review.review_id[:8]}"
        try:
            self._vault.write_curated_note(
                title=title,
                body=body,
                source_session_id=review.review_id,
                marker="cross_agent_review",
                owner=settings.default_owner,
            )
        except (PermissionError, OSError, ValueError):
            pass  # Befunde bleiben als Cards/Review erhalten; Vault-Spur ist best-effort.
