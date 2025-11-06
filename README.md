# LocalBrain (Fiumicino Pilot) — MVP

**Obiettivo:** AI radar locale che aggrega fonti pubbliche (RSS + HTML), classifica/rankizza i contenuti e invia alert via Telegram.  
Questa è una base *senza* dipendenze costose: niente Claude; DB = SQLite; LLM facoltativo.

## Stack
- Python 3.11+
- FastAPI (API)
- SQLite + SQLAlchemy (DB)
- feedparser + requests/BeautifulSoup (ingest)
- python-telegram-bot (notifiche)
- Jinja2 per il templating della dashboard
- (Opzionale) LLM per ranking: usa solo se imposti `LLM_PROVIDER` e API key. Di default usa un **ranker euristico**.

## Avvio rapido
1) Crea un virtualenv e installa:
```bash
pip install -r requirements.txt
```
2) Copia `.env.example` in `.env` e personalizza (Telegram token, città, ecc.).
3) Avvia il DB e crea le tabelle (auto alla prima esecuzione).
4) Lancia l'ingest (raccoglie contenuti dalle fonti):
```bash
python -m scripts.ingest
```
5) Avvia l'API (dashboard e endpoint REST):
```bash
uvicorn app.main:app --reload --port 8080
```
6) Avvia il bot Telegram in un secondo terminale:
```bash
python -m bot.bot
```

## Deployment su Server (46.62.132.83)
Il progetto è deployato sul server e coesiste con:
- **SeniorCare** (porta 8001)
- **AI Wallet Starter** (Node.js)
- **Interview Assistant** (Node.js)
- **AirCoachInterview.it** (sito web)

**Configurazione attuale:**
- Directory: `/var/www/localbrain-mvp/`
- Porta: `8080`
- Nginx: configurato per `localbrain.it` e `www.localbrain.it`
- Scheduler: attivo - ingest automatico ogni ora

**URL LIVE:**
- **Dashboard:** http://localbrain.it/dashboard
- **Health:** http://localbrain.it/health
- **Ingest manuale:** POST http://localbrain.it/admin/ingest-now
- **URL di test (server):** http://46.62.132.83:8080/dashboard

## Config (.env)
- `CITY=Fiumicino`
- `TELEGRAM_BOT_TOKEN=123:abc` (obbligatorio per il bot)
- `TELEGRAM_ALLOWED_USER_IDS=123456789,987654321` (comma-separated; opzionale)
- `LLM_PROVIDER=groq|deepseek|none` (default: none)
- `LLM_API_KEY=...` (facoltativa; usata solo se `LLM_PROVIDER != none`)
- `LLM_MODEL=` (es. `llama-3.1-8b-instant` o `deepseek-chat`)
- `DATABASE_URL=sqlite:///./localbrain.db`
- `FEED_AD_FREQUENCY=3` (opzionale: ogni quanti item inserire uno sponsor nel feed)

## Fonti
Modifica `app/sources/rss_list.json` e `app/sources/html_rules.json` per aggiungere/gestire fonti.  
**Inizio con RSS**, poi HTML (con selettori CSS).

## Categorie supportate (MVP)
- `lavoro`, `bandi`, `eventi`, `annunci`, `casa`, `altro`

## Dashboard, Ads & Bacheca
- `/dashboard` mostra il feed filtrabile con ads intercalati, due slot laterali sticky e una sezione "Professionisti disponibili" con le ultime autocandidature. Footer coerente con l’header (blu LocalBrain): shortcut “Aggiungi attività”, “Pubblica annuncio”, iscrizione Telegram. Le pagine admin mantengono stile uniforme.
- La bacheca `/offers` elenca le autocandidature pubblicate; `/offers/new` è il form pubblico (gli annunci restano in `pending` finché non approvati).
- Gli ads si configurano dal pannello `/admin/ads` (senza login). Gli annunci della bacheca si moderano da `/admin/offers`.
- `/items?include_ads=true` restituisce gli item con sponsor (campo `type=item|ad`).
- `/api/offers` espone le offerte pubblicate (`status_filter`, `city`, `category`).

## Bot Telegram
- Comandi: `/latest`, `/cat <categoria>`, `/offers`.
- Gli ads nel bot rispettano il flag `show_in_feed` (solo sponsor feed).
- `/offers` mostra le ultime 5 autocandidature pubblicate.

## Struttura Ads (tabella `ads`)
- `title`, `url`, `message`
- `show_in_feed` (bool), `sidebar_slot` (`left`, `right`, vuoto)
- `image_url` (facoltativo), `active`, `weight`

## Struttura ServiceOffer
- `title`, `description`, `category`, `city`, `zone`
- `contact_name`, `contact_method`, `rate`, `available_from`, `available_to`
- `status` (`pending`, `published`, `archived`, `rejected`), `highlighted`

## Nuove Funzionalità (Novembre 2025)

### Estrazione Immagini da RSS
- Estrae automaticamente immagini da feed RSS da 5 fonti diverse:
  - `media_content` (tag media:content)
  - `enclosures` (allegati RSS)
  - `media_thumbnail` (thumbnail immagini)
  - `content` (contenuto HTML con immagini)
  - `summary` (riassunto con immagini)
- Immagini salvate come URL (hotlinking) senza occupare spazio locale
- Visualizzazione immagini nella dashboard con stile responsivo

### Documentazione Legale e GDPR
- Privacy Policy, Terms & Conditions, Disclaimer, About Us
- Cookie banner GDPR compliant
- Checkbox accettazione privacy in tutti i moduli
- Footer con link legali su tutte le pagine

### Git Repository
- Repository GitHub privato configurato
- Deployment automatizzato via SCP
- Gestione versioni del codice

## Roadmap breve
- [x] Scheduler (APScheduler) per ingest automatico ogni ora
- [x] Estrazione immagini da RSS feeds (media_content, enclosures, media_thumbnail, content, summary)
- [x] Visualizzazione immagini articoli nella dashboard
- [ ] Filtri/alert per categoria
- [x] Pannello admin upload ads
- [ ] Metriche click-through / analytics
- [ ] Export canale Telegram "broadcast" locale
- [ ] Funzionalità di ricerca nel feed

---
**Brand:** ainextstudio.it — Pilot: Fiumicino

## Attività Locali
- `/businesses` mostra la griglia delle attività locali curate (filtri città/categoria).
- `/businesses/new` modulo pubblico per segnalare una nuova attività.
- `/admin/businesses` (token opzionale) elenca e gestisce gli inserimenti.
- `/api/businesses` espone i dati in JSON.
- `scripts/seed_businesses.py` popola alcuni esempi iniziali.
