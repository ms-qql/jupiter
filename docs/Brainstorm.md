# Brainstorm: Jupiter Micro App Clipboard

Date: 2026-07-08
Status: Converged to MVP feature description for subsequent ABC workflow

## Session Setup

Topic: Jupiter Micro App `Clipboard` for simple file and document exchange between devices connected through the user's Tailscale network.

Goal: Produce a clear feature description suitable for subsequent implementation through the ABC workflow.

Approach: Progressive flow. Start from concrete user journeys, identify the practical MVP, then converge into scope, flows, data expectations, and acceptance criteria.

User context:
- Devices: PC, Mac, iPad, iPhone.
- Network: private Tailscale network.
- Knowledge system: HAL Obsidian vault.
- Primary need: move screenshots, PDFs, and documents between devices without cloud friction.
- Desired interaction model: iOS via native share flow; desktop via browser drag and drop, copy and paste, and later possibly watch folders.

Constraints and assumptions:
- MVP is for the user's own workflow first.
- Tailscale-only access is acceptable for the first version.
- Every item must be automatically stored in an unsorted HAL Inbox.
- HAL condensation is a separate, less frequent activity, for example weekly.
- Clipboard items remain visible until manually deleted.

Preferred energy: practical MVP.

## Initial Framing

The core problem is not generic file sharing. The user needs a cross-device working clipboard:

- iPad screenshots should appear on the PC quickly, ideally as a clipboard item that can be previewed, downloaded, moved, deleted, or copied into the desktop OS clipboard.
- PDF documents should move from PC to iPad with as little friction as possible.
- Mac-local project work, such as immo-check, must connect with a development workflow that is mostly operated from a VPS and PC.
- All incoming material should be preserved automatically in HAL as raw input, then later condensed into structured notes or folders.

## Divergence

### User Journeys

**[Use Case #1] iPad-Screenshots zum PC**
_Concept:_ On iPad, a screenshot is sent to Jupiter Clipboard through the iOS share flow. On PC, it appears in the Clipboard list and can be previewed, downloaded, deleted, or copied into the OS clipboard.
_Novelty:_ The app behaves as a temporary cross-device work buffer, not just a cloud folder.

**[Use Case #2] Mac-lokale Dateien in VPS/PC-Workflow**
_Concept:_ Files produced or used locally on the Mac are placed into Jupiter Clipboard so they can be accessed from the PC/VPS working context.
_Novelty:_ The feature bridges local app constraints with the user's main remote development setup.

**[Use Case #3] PDFs vom PC aufs iPad**
_Concept:_ A PDF is added on PC through drag and drop, copy and paste, or upload. On iPad, the item can be opened, previewed, downloaded, or shared onward to another app.
_Novelty:_ The same clipboard works bidirectionally across desktop and mobile.

### Core Product Shape

**[Core Idea #4] Mehrfach-Clipboard statt Single Clipboard**
_Concept:_ The clipboard is a chronological list of items, each with preview, metadata, actions, and status. It supplements the OS clipboard rather than replacing it.
_Novelty:_ Multiple files remain available instead of being overwritten by the next copy action.

**[HAL Idea #5] Clipboard kondensieren**
_Concept:_ Selected or all Inbox material can later be condensed into structured HAL notes, similar to session condensation.
_Novelty:_ Transfer material becomes curated knowledge rather than stale file clutter.

### Storage

**[Storage #6] HAL Inbox als Rohspeicher**
_Concept:_ Every Clipboard item is immediately and automatically stored in an unsorted HAL Inbox, including the original file and metadata.
_Novelty:_ No manual "save to HAL" decision is needed during daily transfer work.

**[Processing #7] Kondensierung als zweiter Schritt**
_Concept:_ A separate process periodically extracts useful content from the raw HAL Inbox, condenses it, and stores the result in the appropriate HAL location.
_Novelty:_ Raw capture and knowledge curation are separated cleanly.

### Inputs

**[Input #8] iOS Share Sheet zuerst**
_Concept:_ iPhone and iPad can send screenshots, PDFs, and files to Jupiter Clipboard through the native share flow.
_Novelty:_ Mobile entry feels native and avoids browser upload friction.

**[Input #9] Desktop Drag & Drop im Browser**
_Concept:_ PC and Mac users can open the Micro App and drag files directly into the Clipboard list.
_Novelty:_ Works without installing a desktop helper.

**[Input #10] Desktop Copy/Paste in der App**
_Concept:_ Screenshots or supported copied file content can be pasted into the web app.
_Novelty:_ Matches the natural desktop workflow for screenshots and documents.

**[Input #11] Beobachteter Ordner spaeter**
_Concept:_ A future local watch folder on Mac/PC could automatically place new files into Clipboard.
_Novelty:_ Very convenient, but likely requires a local helper and is not necessary for MVP.

### Outputs

**[Output #12] Vorschau und Oeffnen**
_Concept:_ Items can be viewed in the app when the browser supports the file type, especially images and PDFs.
_Novelty:_ The clipboard is useful as a short-term work context, not only as a transfer channel.

**[Output #13] Download auf Zielgeraet**
_Concept:_ Each item can be downloaded to PC, Mac, iPad, or iPhone.
_Novelty:_ One consistent retrieval model works across devices.

**[Output #14] iOS Weiterteilen**
_Concept:_ On iPhone and iPad, an item can be shared onward through the native iOS share mechanism when supported by the browser/PWA environment.
_Novelty:_ Enables practical PC-to-iPad PDF movement.

**[Output #15] Desktop Copy-to-Clipboard**
_Concept:_ Supported items, especially images, can be copied from the Clipboard list into the desktop OS clipboard.
_Novelty:_ iPad screenshots can land on PC and be pasted directly into the next tool.

### Lifecycle

**[Lifecycle #16] HAL-Kondensierung als Wochenprozess**
_Concept:_ Clipboard continuously stores raw material in HAL Inbox; condensation is run separately, for example once per week.
_Novelty:_ Daily transfer stays fast while long-term knowledge hygiene remains possible.

**[Lifecycle #17] Persistente Clipboard-Liste**
_Concept:_ Items remain visible in the active Clipboard list until manually removed.
_Novelty:_ The list behaves as a reliable work buffer, not a volatile queue.

**[Lifecycle #18] Manuelles Loeschen**
_Concept:_ The user can delete individual items from the active Clipboard list.
_Novelty:_ The MVP should prefer removing items from the active list while preserving the HAL Inbox raw file unless explicitly designed otherwise.

## Convergence

### MVP Feature Description

Build a Jupiter Micro App named `Clipboard` that provides a private, Tailscale-accessible, cross-device file clipboard for PC, Mac, iPad, and iPhone.

The app lets the user add screenshots, PDFs, and documents from mobile and desktop devices into a persistent Clipboard list. Each uploaded item is automatically copied into an unsorted HAL Inbox as raw material. The active Clipboard list shows recent and older items until the user manually deletes them. Items can be previewed, downloaded, opened, moved or shared where supported, and copied back into the desktop clipboard for supported file types.

The first implementation focuses on transfer and raw capture. HAL condensation is explicitly out of the daily transfer flow and should be implemented or invoked as a separate weekly activity that reads from the HAL Inbox, extracts relevant content, condenses it, and stores structured outputs in the correct HAL locations.

### MVP Scope

In scope:
- Tailscale-accessible Jupiter Micro App page.
- Chronological Clipboard item list.
- Upload from desktop through drag and drop.
- Upload from desktop through paste where browser APIs support it.
- Mobile upload path optimized for iOS share flow.
- File support for screenshots/images, PDFs, and generic documents.
- Automatic raw storage of each item in HAL Inbox.
- Item preview for images and PDFs.
- Item download.
- iOS onward sharing where the web/PWA environment supports it.
- Desktop copy-to-clipboard for supported item types, especially images.
- Manual deletion/removal from active Clipboard list.

Out of scope for MVP:
- Local Mac/PC watch folder.
- Automatic semantic filing into HAL.
- Weekly HAL condensation implementation, unless started as a separate feature.
- Multi-user permissions beyond the current private Tailscale assumption.
- Public internet access.
- Complex retention rules or automatic cleanup.
- Full replacement of OS-level clipboard synchronization.

### Suggested Data Model

Clipboard item:
- `id`: stable unique identifier.
- `created_at`: upload timestamp.
- `source_device`: optional device label, for example `ipad`, `pc`, `mac`, `iphone`.
- `source_method`: `ios_share`, `drag_drop`, `paste`, or `upload`.
- `original_filename`: original file name when available.
- `display_name`: editable or derived name.
- `mime_type`: detected MIME type.
- `size_bytes`: file size.
- `storage_path`: internal app storage path or object reference.
- `hal_inbox_path`: path of copied raw item in HAL Inbox.
- `status`: active, removed_from_clipboard, or error.
- `notes`: optional short text note for future context.

HAL Inbox target:
- Suggested base path: `/home/dev/tools/Hal/00 Inbox/Clipboard/` or the existing HAL Inbox convention if one already exists.
- Suggested per-item naming: `YYYY-MM-DD_HHMMSS_<source-device>_<slug-or-id>.<ext>`.
- Suggested sidecar metadata: `YYYY-MM-DD_HHMMSS_<source-device>_<slug-or-id>.md` or a central index, depending on existing HAL patterns.

### Primary User Flows

Flow 1: iPad screenshot to PC
1. User creates or selects a screenshot on iPad.
2. User opens iOS share flow and sends it to Jupiter Clipboard.
3. Clipboard receives the item, stores the raw file in HAL Inbox, and adds an active list item.
4. User opens Clipboard on PC.
5. The screenshot is visible in the list with preview.
6. User copies it into the desktop clipboard, downloads it, or deletes it from the active list.

Flow 2: PC PDF to iPad
1. User opens Clipboard on PC.
2. User drags a PDF into the app.
3. Clipboard stores the PDF in HAL Inbox and adds it to the active list.
4. User opens Clipboard on iPad.
5. User previews, downloads, opens, or shares the PDF onward.

Flow 3: Mac local artifact to PC/VPS workflow
1. User creates or finds a file on Mac.
2. User drags it into Clipboard or pastes it into the app.
3. Clipboard stores the item in HAL Inbox and adds it to the active list.
4. User accesses it from PC while operating the VPS workflow.

Flow 4: Weekly HAL condensation
1. User runs a separate HAL condensation activity.
2. The process reads relevant Clipboard Inbox items.
3. It condenses useful content and stores it in the appropriate HAL location.
4. Raw Inbox remains available unless a separate cleanup policy is defined.

## Acceptance Criteria

1. The user can open the Jupiter Clipboard Micro App from another Tailscale-connected device.
2. The user can drag and drop an image, PDF, or document from PC/Mac into the app.
3. The user can paste supported clipboard content into the app from desktop.
4. The user can send at least images and PDFs from iOS/iPadOS into the Clipboard through the best available share-compatible path.
5. Every accepted item appears in the Clipboard list without manual refresh or after a clearly available refresh action.
6. Every accepted item is automatically stored in the configured HAL Inbox.
7. The Clipboard list displays useful metadata: name, type, source, timestamp, and size.
8. Image and PDF items can be previewed in the app.
9. Any item can be downloaded from the app.
10. Supported image items can be copied from the app into the desktop clipboard.
11. On iOS/iPadOS, supported items can be opened or shared onward where browser/PWA APIs allow it.
12. The user can manually remove an item from the active Clipboard list.
13. Removing an item from the active Clipboard list does not delete the HAL Inbox raw file in the MVP.
14. The app handles unsupported file types with a clear error or generic-file fallback.
15. The app handles upload failures without creating a misleading active item.

## Recommended Implementation Sequence

1. Define storage paths and HAL Inbox convention.
2. Build backend endpoints for upload, list, retrieve, delete-from-active-list, and metadata.
3. Implement automatic HAL Inbox copy during upload.
4. Build the Clipboard list UI with preview, download, copy, and delete actions.
5. Add desktop drag and drop.
6. Add desktop paste support.
7. Validate iOS share/open-in path and implement the most reliable approach for the current Jupiter stack.
8. Add basic tests for upload, HAL storage, list retrieval, and delete semantics.
9. Add a manual smoke test across PC/Mac/iPad if available.

## Open Decision Points

1. Exact HAL Inbox path and naming convention.
2. Whether the app already has a device identity mechanism or whether source device is manually inferred/labeled.
3. Whether uploaded files are stored only in HAL Inbox or also in a separate app storage location.
4. Exact technical path for iOS share integration, depending on whether Jupiter Micro Apps are PWAs, native wrappers, Shortcut-compatible endpoints, or browser-only pages.
5. Maximum file size for MVP.
6. Whether active-list deletion should keep app storage but mark hidden, or remove app storage while preserving the HAL Inbox copy.
7. Authentication expectations inside Tailscale.

## Top Priority

The first implementable slice should be:

Desktop-to-device and device-to-desktop Clipboard list with automatic HAL Inbox raw storage.

Success metric:
- The user can move an iPad screenshot to PC and a PC PDF to iPad using Jupiter Clipboard, with both files automatically present in HAL Inbox.

Suggested follow-up skill:
- Use `abc-requirements` or the relevant ABC implementation flow to turn this MVP description into implementation tickets and acceptance tests.
