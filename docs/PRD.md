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

## v2.7 (Nov 2026): TV remote
- Live area with Live TV, Radio, Guide (EPG with now/next, channel numbers) and Favorites (on device)
- Full-screen live player: Channel Up/Down, Channels/Stations picker (stream keeps playing until OK), tuning banner, Retry / Return to previous stream, rapid-switch safety (one stream, one audio output), Play/Stop with reconnect, Pause/Rewind/Go Live on time-shift streams, program details
- On-demand TV controls: play/pause, seek bar, resume, next/previous, captions, audio tracks, quality, speed, full screen with OK-to-reveal
- Back closes overlays first and restores focus to the item the viewer came from; media and channel keys for Tizen, webOS, Android TV and HbbTV
- Simulcast audit: the Studio's 10 destinations were display-only; no simulcast was functional before this release

## v2.8 (Nov 2026): Broadcasting phase 1
- MediaMTX media server (RTMP / RTMPS / SRT ingest, HLS out, WebRTC ready); LoNo API validates stream keys (http auth)
- Rotatable per-creator stream key; destinations by server URL + key, encrypted at rest, write-only
- Private test sessions with signed preview; go live on LoNo Live TV/Radio; idempotent create/start/stop
- Simulcast relays (ffmpeg stream copy), one per destination, with live/failed state, readable errors, targeted retry, auto-resume after encoder reconnect
- Recording (fragmented MP4 parts joined at the end), private by default; publish now, schedule or keep private
- Session events for webhooks; no stream keys in logs; 38/38 integration checks with stand-in platforms

## v2.9 (Nov 2026): Broadcasting phase 2
- Live Studio: Devices & Sources (cameras, mics, interfaces, capture cards; rename, preview, quality, meters, mute, separate monitoring, hot-swap, disconnect/reconnect), external encoder panel with tool guides, destinations UI, private test with "What LoNo receives", go live, per-destination status/Retry, activity log, end, recordings publish/schedule/private
- Browser camera via WHIP proxied through the API (key stays server-side); browser codecs (VP8/Opus) converted once to H.264/AAC for viewers, destinations and recording
- Fix: Permissions-Policy now allows camera/mic/screen for LoNo itself

## v3.0 (Nov 2026): Live Control Room
- Rooms with secret, expiring contributor invitations (phone/laptop, or encoder for crews and venues); private waiting area
- Producer Control Room: multiview with meters, Preview/On Air with TAKE, single/split/clip/standby scenes, lower thirds with optional location, cue messages, talkback, mute, remove
- Contributor page: ON AIR / cued indicators, mix-minus audio return, audio-only, auto and manual reconnect
- One continuous program composited in the producer's browser into the broadcast session (LoNo + destinations)
- Automatic fallback to the anchor/standby on network evidence; destinations reconnect automatically after a drop
- Acceptance test 24/24 (anchor + 2 reporters in separate processes, drop and reconnect, mix-minus verified with ffmpeg)

## v3.0 (Nov 2026): Creator API
- Developer Access in Creator Studio: integrations with scopes, live/test environment, token shown once, rotate, revoke, webhook secret, delivery log
- /api/v1 for sessions, ingest, destinations, recordings and Control Room production; idempotent create/start/stop; per-integration rate limit; audit
- Signed webhooks with retries; SSRF-safe webhook URLs; reference at /api/docs; guide and examples in docs/CREATOR-API.md
- Private recordings now need a signed, expiring link (the file URL alone was enough before)
- Live API test 14/14 against the real media server

## v3.1 (Nov 2026): Commercial pilot (sponsored replay passes)
- Pilot mode: $LONO earned, redeemable, non-transferable; simulated purchases, signup bonus, new staking and $LONO creator payouts off; existing stakes stop accruing at pilot start; balances and history untouched
- Staff campaigns: organizer, sponsor, replay, earning rule, points price, inventory, dates, access period; money recorded separately; opens only after sponsor payment, distribution permission and server-checked playback readiness; pause/resume/close; full change history
- Fans: Offers, earn by verified watching, confirm and claim, My passes, mobile replay player
- Consistent claim (reserve pass → deduct points → activate, undone on failure; idempotent; crash repair); last-pass race safe
- Protected replay: files 403 directly; signed playback URL bound to the fan's cookie; access ends on reversal or expiry
- Reversal: points restored once; pass returned only while the offer is open
- Staff report with reconciliation; aggregate sponsor report and CSV; rebooking field
- Staging rehearsal 27/27 on real MongoDB; operator guide

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
