# LoNo — Product Requirements Document

## Original Problem Statement
Build LoNo, the world's first unified hybrid media, broadcasting, streaming, learning & Web3 platform combining Digital TV, Radio, Live Streaming, VOD/AOD, Podcasts, Satellite, IPTV, OTT, LMS, Creator Economy, AI Media Platform, Token Economy ($LONO), Community, Marketplace, and Global Broadcasting Network. Netflix-level UX, mobile-first, dark mode primary, accessibility compliant.

## User Choices (MVP)
- Modules: Streaming (VOD/Live TV/Radio) + Creator Channels + Auth + Wallet/Token dashboard
- Auth: Email/Password (JWT) + Google sign-in
- AI: recommendations + chatbot + summarization + subtitles + thumbnails
- Web3: simulated $LONO token (internal MongoDB ledger) — wallet, staking, watch-to-earn, DAO
- Payments: Stripe test key + simulated crypto/token purchase

## Personas
- Viewer/Listener — watches, listens, earns $LONO
- Creator — uploads, monetizes, simulcasts
- Investor / Token Holder — stakes, votes, tracks tokenomics
- Compliance Officer — reviews utility token disclosures

## Architecture (current)
- Backend: FastAPI + Motor (async MongoDB) + JWT + bcrypt + Anthropic SDK (Claude) + Stripe
- Frontend: React 19 + Tailwind + shadcn/ui + Recharts + sonner + framer-motion + lucide-react
- Fonts: Clash Display (headings) + Satoshi (body) via Fontshare
- All API routes prefixed with `/api`; frontend uses `REACT_APP_BACKEND_URL`

## Implemented (Feb 2026)
- Authentication: register/login (JWT), Google sign-in exchange, /auth/me
- Content: seeded 29 items across 8 kinds (movie, series, short, music, podcast, live_tv, live_radio, course), 6 channels, 4 governance proposals
- Home: Netflix-style hero + 9 rails (Featured, Trending, Top 10, Originals, New, Movies, Series, Podcasts, Music, Continue Watching when logged in)
- Watch page: video/audio player, AI Summary generator, similar content, watch-to-earn (1 LONO/min capped 10 per event), Whisper caption generator with in-player `<track>` element
- Live: /live shows Live TV & Live Radio grids with pulse indicators
- Browse: /browse/:kind category views
- Search: /search?q=
- Channel: /channel/:id with banner, avatar, uploads grid, subscribe CTA
- Creator Studio: auto-provisioned channel, stats (subscribers/views/revenue/LONO), 14-day chart, simulcast destinations panel (10 platforms), upload dialog with real file uploads (thumbnail + media, progress bar) to local or S3 storage
- Object storage: `/api/storage/upload` (multipart, 100MB cap, MIME whitelist) → proxied `/api/files/{path}` playback URLs. `resolveMedia()` helper on frontend transparently prefixes backend origin.
- Whisper transcription: `/api/ai/transcribe/{content_id}` (verbose_json → VTT with segment timing), cached in Mongo, served via `/api/content/{id}/subtitles.vtt`.
- LoNo Wallet: total balance hero, available/staked/earned, stake dialog (30/90/180/365 days at 8-35% APY), unstake with pro-rata rewards, simulated $LONO purchase, Stripe premium upgrade, transactions table
- Tokenomics: supply metrics, 7-day price chart, allocation pie, treasury/creator/education/community funds
- Governance: 4 proposals, for/against/abstain voting weighted by balance+2×staked, one-vote enforcement
- AI Assistant: floating chat FAB (Claude Sonnet 4.5) with persistent session
- Sonner toasts for feedback across app

## v2.0 rebuild (Nov 2026)
- Removed every Emergent dependency: Claude via the Anthropic API, captions via any OpenAI-compatible speech-to-text endpoint, local/S3 storage, Google Identity Services sign-in, no platform scripts
- Backend split into modules (`backend/app/`), atomic ledger, optional features report via `/api/config`
- Watch-to-Earn verified server-side (heartbeats, per-title and daily caps), replacing the client-claimed seconds
- LMS: 3 courses, lessons, quizzes, Learn-to-Earn, SHA-256 verifiable certificates
- Stripe webhook updates plans; demo token purchase capped and switchable
- Likes, My List, subscriptions, member proposals, real creator view charts, mobile tab bar
- Docker Compose deploy, 20 API tests

## v2.1 (Nov 2026)
- Course builder: creators draft, edit, publish and unpublish courses with lessons, video uploads and quizzes
- Platform-set learner reward (10 $LONO), creator payout per certificate (2 $LONO), no self-rewards
- AI-drafted quiz questions from lesson text (Claude), reviewed by the creator before saving
- Frontend build lint restored to the standard React rules (undefined variables now fail CI)
- One-command launchers (start.cmd / start.sh) and GitHub Actions CI

## v2.2 (Nov 2026)
- Course reviews and ratings: verified learners only, one editable review each, averages and star breakdown on the course, Learn list, catalogue cards and Studio

## v2.3 (Nov 2026)
- Sign-in protection: pause after 5 failed attempts per email+network; 10 sign-ups per network per hour
- Wallet "Your earnings": 7/30/90-day stacked chart by source (watching, courses, staking, creator payouts, bonuses), verified watch time, viewing streak
- Profile "Recently watched" with progress and clear-history; players resume where you left off

## v2.4 (Nov 2026)
- Settings: display name, change/set password, download my data (GDPR access), delete account (GDPR erasure, aggregates kept anonymously)
- Security headers on every response; API responses not cached
- Faster first load: pages download on demand (main bundle about 155 kB gzipped, down from about 300 kB), lazy images, safe reload after deploys

## v2.5 (Nov 2026)
- Admin console (ADMIN_EMAILS): overview, review reports (hide, dismiss, restore), user suspension, course takedown with creator-visible note
- Compliance records: versioned terms consent at sign-up and re-consent banner; audit log of consents, data downloads, deletions, password changes and admin actions; CSV export with formula-injection protection; erasure evidenced by email hash only
- Terms page with plain-language $LONO disclosure; disclosure line on the token page

## v2.5.1 (Nov 2026)
- Admin accounts are created by the server at startup from ADMIN_EMAILS (msf@ciu.edu.lr), with a one-time password in the server log; an email alone never grants admin, since emails aren't verified yet
- `python -m app.admin_setup` to grant/remove admin and reset passwords on a real database
- Support contact lono@ciu.edu.lr on the Terms page
- Fix: sign-in responses carry is_admin / needs_terms, so the Admin menu and terms banner appear without a reload

## v2.6 (Nov 2026)
- Installable app: web manifest, icons (incl. maskable and iOS), service worker (fast repeat visits, image cache, offline screen), Install banner and Settings entry, iOS instructions
- TV mode: auto-detected on TV browsers or with ?tv=1; spatial remote navigation (arrows/OK/Back incl. Tizen 10009 and webOS 461), larger type, focus highlight, overscan margins
- Player: adaptive HLS via hls.js (loaded on demand), quality menu, data-saver start at lowest quality, Media Session controls, picture-in-picture, Cast to TV, playback speed
- Data saver: automatic on Save-Data/2G/3G; lighter images, no preloading
- TV packages: Samsung Tizen and LG webOS hosted apps; Android TV/Fire TV WebView wrapper (template); Android TWA support via /.well-known/assetlinks.json; docs/DEVICES.md

## Backlog (post-MVP priorities)
- **P1**: Offline downloads for audio and video; HLS transcoding of uploads (Mux/Cloudflare Stream); Apple TV and Roku native apps; email verification and password reset by email (needs an email provider); KYC/AML provider integration (the admin console and audit log are ready for it); notifications; on-chain anchoring for certificates; Simulcast RTMP orchestration; Watch parties & multi-profile
- **P1**: Compliance dashboard (FCC/DMCA/KYC/AML/GDPR) — configurable modules per jurisdiction
- **P2**: Real blockchain settlement layer, WalletConnect / MetaMask integration
- **P2**: Marketplace (NFT, merch, tickets, licenses), programmatic ads platform, developer portal + SDK
- **P2**: SSO, biometric login, passkeys, 2FA

## Known Limitations
- $LONO is a simulated internal ledger only (no on-chain settlement)
- Tokenomics supply figures and price are illustrative constants
- Live TV/Radio channels play sample media; no live ingest yet
