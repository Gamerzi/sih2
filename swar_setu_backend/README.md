# Swar Setu — Python Backend (separate from the Vercel frontend)

JSON API only. It serves no HTML, so your hosted frontend is not affected. Deploy it separately
(Render, Railway, Fly.io, a VM…) and point the frontend's `fetch()` calls at its URL.

## Files (one feature per file)

| File | Role |
|---|---|
| `agents/agent1_interview.py` | Question generator: one question at a time, in the user's language, until nothing required is missing |
| `agents/agent2_profile.py` | Profile builder: transcript to structured profile, edit, confirm |
| `agents/agent3_nsqf_matcher.py` | NQR/NSQF course search: deterministic scoring on the confirmed profile |
| `agents/agent4_livelihood.py` | Local opportunity finder: runs the 4 retrievers, filters, verifies, ranks |
| `retrievers/ncs_retriever.py`, `state_portal_retriever.py`, `udyam_retriever.py`, `myscheme_retriever.py` | One module per official source |
| `retrievers/base.py` | Shared normalised record shape + seed fallback |
| `nqr_repository.py` | Reads qualifications from MongoDB or the sample JSON |
| `llm.py` | Only place that talks to Groq. Works without a key (rule-based fallbacks) |
| `session_store.py` | Journey state; in-memory, or MongoDB if `MONGODB_URI` is set |
| `scripts/import_nqr_to_mongo.py` | Load a real NQR export into MongoDB |
| `main.py`, `config.py`, `utils.py` | App entry, env config, helpers |

## Run

```bash
pip install -r requirements.txt
cp .env.example .env        # add GROQ_API_KEY, and your Vercel URL in ALLOWED_ORIGINS
uvicorn main:app --reload --port 8000
# interactive docs: http://localhost:8000/docs
```

## API flow (the frontend calls these in order)

1. `POST /api/interview/start` `{"language":"te"}` → `{session_id, question, done}`
2. `POST /api/interview/answer` `{session_id, message}` → next `question`, until `done: true`
3. `GET /api/profile/{id}` → show the profile; `PUT /api/profile/{id}` `{"fields":{...}}` to edit
4. `POST /api/profile/{id}/confirm` → unlocks the next two steps (they return 409 otherwise)
5. `POST /api/nsqf/match` `{session_id}` → `qualifications[]` + spoken `explanation`
6. `POST /api/opportunities/find` `{session_id}` → `opportunities[]` (each with `source_url`) + `explanation`

Speak `question` / `explanation` with TTS in the frontend, and send recognised speech as `message`.
Replacing the current single `/api/chat` call is the only frontend change needed.

## Important: placeholder data

* `data/nqr_sample.json` (11 records) and the two NCS job entries in `data/opportunities_seed.json` are **placeholders** to test the pipeline. Responses flag them (`data_source: "sample"`, `is_sample: true`, and a note).
* The scheme entries (PM Vishwakarma, PMEGP, Stand-Up India, Udyam, MUDRA) point to official sites; verify their wording and links before demo day.
* The four `fetch_live()` methods are TODO stubs: NCS / myScheme / Udyam / NQR access methods and licensing still need verifying, as your project notes say.
* `data/state_portals.json` holds main state-government sites only; swap in each state's employment portal once verified.
