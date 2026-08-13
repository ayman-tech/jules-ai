# Jules AI — Company Second Brain + Research Assistant

Jules AI is an organization-aware AI chat application that combines permission-scoped company knowledge with optional live web research. Employees can select several authorized knowledge bases per conversation; owners and admins manage access and review shared knowledge, duplicates, conflicts, unanswered questions, and reported answers.

## What is included

- Private, persistent chat with three memory layers: recent conversation context, rolling summaries, and user-only past-chat retrieval.
- Company knowledge bases with audited per-user access, multi-file uploads, immutable versions, durable ingestion jobs, and source previews.
- Permission filtering before retrieval, PostgreSQL full-text search plus 768-dimensional pgvector search, reciprocal-rank fusion, and parent-section expansion.
- PDF, DOCX, PPTX, XLSX, CSV, text, and Markdown ingestion. PDFs support page-aware text, tables, Document AI layout parsing when configured, and Gemini vision descriptions for charts and figures.
- Exact and near duplicate detection, new-version review, potential contradiction detection, and an admin conflict-resolution workflow.
- User-controlled Google Search grounding, on by default for new users. The composer can override the saved preference per conversation.
- Separate Company source and Web source citations. Public research is isolated from internal retrieval so company document text never reaches the Google Search call.
- Chat-derived knowledge proposals that require owner/admin approval before becoming shared evidence.
- Private, editable DOCX and PPTX generation with durable jobs, immutable revisions, organization branding, source citations, previews, and authenticated downloads.
- Structured JSON API logging and development-only transcript logging.

## Run locally with SQLite

Prerequisites: Node.js 22+, Python 3.11+, and [uv](https://docs.astral.sh/uv/).

SQLite is convenient for basic local development and has a deterministic retrieval fallback. PostgreSQL with pgvector is required for the production knowledge-search path.

1. Install dependencies:

   ```bash
   npm install
   cd services/api && uv sync --extra dev && cd ../..
   ```

2. Copy the example environment values:

   ```bash
   cp .env.example services/api/.env
   ```

3. In `services/api/.env`, set your AI Studio key:

   ```dotenv
   GOOGLE_API_KEY=your_google_ai_studio_key
   ```

   Leave `GOOGLE_CLOUD_STORAGE_BUCKET` and `DOCUMENT_AI_PROCESSOR_NAME` empty for local disk storage and local PDF parsing. No GCS setup is needed for this mode.

4. Apply migrations:

   ```bash
   cd services/api && uv run alembic upgrade head && cd ../..
   ```

5. Start the API, web app, ingestion worker, and artifact worker together:

   ```bash
   make run
   ```

   Press `Ctrl+C` to stop every process. You can still run `make api`,
   `make web`, `make worker`, or `make artifact-worker` separately when debugging one service.

6. Open `http://localhost:3000`. Development mode seeds a sample organization and trusts the local `X-User-ID` / `X-Organization-ID` headers.

If `GOOGLE_API_KEY` is empty, chat uses a deterministic demo response. Document parsing and local search still work, using stable local embeddings for development.

## Test real accounts locally with Firebase

The default development auth mode intentionally skips sign-in and opens the seeded workspace. To exercise account creation, email verification, invitations, and multi-organization switching locally:

1. In Firebase Console, create or select a project. Under **Authentication → Sign-in method**, enable **Email/Password**. Configure the password policy and verification/reset templates under Authentication settings. Follow Firebase’s [password authentication](https://firebase.google.com/docs/auth/web/password-auth) and [user management](https://firebase.google.com/docs/auth/web/manage-users) guides.
2. Keep [email-enumeration protection](https://docs.cloud.google.com/identity-platform/docs/admin/email-enumeration-protection) enabled in **Authentication → Settings → User actions**.
3. Add `localhost` and any other local hostname you use to **Authentication → Settings → Authorized domains**.
4. Register a Web app and copy its public configuration into `apps/web/.env.local`:

   ```dotenv
   NEXT_PUBLIC_API_URL=http://localhost:8000/v1
   NEXT_PUBLIC_AUTH_MODE=firebase
   NEXT_PUBLIC_FIREBASE_API_KEY=...
   NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
   NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-project
   NEXT_PUBLIC_FIREBASE_APP_ID=...
   ```

5. In `services/api/.env`, switch the API to Firebase and identify the project:

   ```dotenv
   AUTH_MODE=firebase
   FIREBASE_PROJECT_ID=your-project
   ```

6. Give Firebase Admin local credentials with either `gcloud auth application-default login` or a narrowly scoped service-account JSON referenced by `GOOGLE_APPLICATION_CREDENTIALS`. Never place a service-account JSON or Firebase Admin private key in a frontend environment variable.
7. Run `make run`. It applies pending migrations before starting the API, worker, and web app. Visit `/sign-up`; verified accounts with no active membership are sent to `/onboarding`.

Firebase Web API keys are public app identifiers, not Admin credentials. The API still independently verifies every Firebase ID token. In production mode it never trusts `X-User-ID`.

Invitations are deliberately manual: an owner/admin creates or resends one, copies the one-time link, and shares it with the exact invited email address. Jules stores only the SHA-256 token hash; the raw token is returned only in that create/resend response. Rotating an invitation invalidates its previous link.

## Run the complete PostgreSQL/pgvector stack

The Compose database image includes the vector extension, and a separate worker consumes durable ingestion jobs:

```bash
docker compose up --build
```

When running the container stack with real Gemini calls, pass `GOOGLE_API_KEY` to the API and worker through an uncommitted Compose override or your shell/environment management. Do not commit the key.

## Knowledge workflow

1. An owner/admin creates a knowledge base and grants explicit access.
2. Any member with access uploads files or new versions.
3. The worker parses, chunks, embeds, and checks the upload for duplicates and potential conflicts.
4. Employees select one or more knowledge bases with the brain control in chat.
5. Retrieval first applies organization, user-access, and selected-space filters. Only then are keyword and vector results ranked.
6. Answers cite document, immutable version, page/section, and effective-date metadata. Removed access takes effect on the next retrieval.
7. Chat content remains private. “Save to Knowledge” creates a proposal; it is not shared until approved.

Owners/admins use **Knowledge Review** for conflicts, proposals, unanswered questions, reported answers, and failed or low-confidence extraction.

## Editable documents and presentations

Choose **Create → Document (.docx)** or **Create → Presentation (.pptx)** in the chat composer, or ask Jules directly to create a Word document or PowerPoint. The selected knowledge bases, web-search state, model, effort, and attachments are snapshotted into the generation job. PDF export is intentionally not included; download the editable file and export it from Word or PowerPoint.

Generation runs in a separate durable worker. The chat card survives refresh and shows planning, rendering, validation, completion, failure, or cancellation. Completed files can be previewed, downloaded, revised into immutable versions, deleted, or explicitly saved into an accessible knowledge base.

Owners/admins upload one organization-wide Word template under **Settings → Organization document template**. Jules preserves its page geometry, letterhead, headers, footers, styles, numbering, and table styling while discarding sample body content. Upload a single-section `.docx` up to 15 MB; `.dotx`, macros, ActiveX/OLE content, external relationships, and remote templates are rejected. A replacement becomes active only after structural and visual validation, so the previous validated template remains available if validation fails.

Organization templates are used by default for DOCX generation and can be disabled per request in the Create menu. Each artifact version records the exact organization-template version used; revisions inherit it unless the user explicitly selects the currently active template. PPTX files use Jules’ built-in presentation themes. Generated files remain private to their creator, and downloads and revisions re-check organization membership and current access to every knowledge base used by the file.

Local development structurally validates Office files even when LibreOffice is absent. Install LibreOffice and Poppler to enable local page/slide previews and Gemini visual QA. The provided artifact-worker container already includes these tools and bundled fonts.

## Web research isolation

Web search starts from each user’s Settings preference and can be changed in the composer without altering that preference. When enabled, Jules performs an isolated Google-grounded research call using only the user-authored question. Retrieved internal document text, private chat memory, and custom instructions are not included in that search call. A second call synthesizes public findings with authorized company evidence.

Company sources define company policy and decisions. Public evidence supplements them and never overrides them automatically. A disagreement is presented as Company position versus Current external evidence.

Chat and generated artifacts use one visible citation sequence (`[1]`, `[2]`, …) across company and web evidence. Source type remains structured metadata for the grouped source cards. Comprehensive DOCX requests use the deep-research pipeline: a bounded research plan, primary-source preferences, content QA, and one corrective drafting pass. Generated research documents include linked sources, document metadata, an updateable contents field, and cited chart data. Set `ENHANCED_RESEARCH_DOCUMENTS=false` to return artifact planning to the standard profile without changing existing files.

## Optional GCS and Document AI

Local development does not require these services. To exercise cloud storage/layout parsing locally, configure:

```dotenv
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_STORAGE_BUCKET=your-private-bucket
DOCUMENT_AI_PROCESSOR_NAME=projects/PROJECT/locations/LOCATION/processors/PROCESSOR_ID
```

Authenticate Application Default Credentials (`gcloud auth application-default login`) and grant the local identity only the bucket and Document AI processor permissions it needs. Original files are stored under organization/knowledge-base/document/version keys.

## Logging

The API writes metadata-only JSON Lines to stderr and `services/api/logs/api.jsonl`. Each response carries `X-Request-ID`. Files rotate at 10 MB and retain five backups.

Development can also write sensitive prompt/response chains to `services/api/logs/chat-transcripts.jsonl`. This file is gitignored and is forcibly disabled outside development even if requested.

```bash
jq 'select(.request_id == "REQUEST_ID")' services/api/logs/api.jsonl
tail -n 20 services/api/logs/chat-transcripts.jsonl | jq .
```

General logs never contain document text, search-query content, authorization headers, database URLs, API keys, attachment bytes, or private chat content.

## Validation

```bash
npm test
```

This runs frontend lint, a production Next.js build, and API tests covering tenancy, request IDs, logs, role permissions, knowledge ingestion/retrieval, duplicates, conversation source snapshots, saved web defaults, and ambiguity events.

## Service map

- `apps/web` — Next.js UI, brain/web composer controls, Knowledge, and Knowledge Review.
- `services/api/app/main.py` — organization-scoped HTTP/SSE API.
- `services/api/app/knowledge.py` — parsing, embeddings, hybrid retrieval, and conflict candidates.
- `services/api/app/knowledge_worker.py` — durable ingestion worker.
- `services/api/app/artifact_worker.py` — durable editable-file generation worker.
- `services/api/app/artifacts.py` — declarative planning, DOCX/PPTX rendering, source checks, and QA.
- `services/artifact-renderer` — controlled PptxGenJS renderer.
- `services/api/app/agent.py` — isolated Google-grounded research and final ADK synthesis.
- `services/api/app/storage.py` — local/GCS originals.
- `services/api/alembic` — additive schema migrations.

Drive, Slack, Notion, Confluence, SharePoint, and other source connectors remain later-phase integrations.
