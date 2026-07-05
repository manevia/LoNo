# LoNo — Product Requirements Document

## Original Problem Statement
Build LoNo, the world's first unified hybrid media, broadcasting, streaming, learning & Web3 platform combining Digital TV, Radio, Live Streaming, VOD/AOD, Podcasts, Satellite, IPTV, OTT, LMS, Creator Economy, AI Media Platform, Token Economy ($LONO), Community, Marketplace, and Global Broadcasting Network. Netflix-level UX, mobile-first, dark mode primary, accessibility compliant.

## User Choices (MVP)
- Modules: Streaming (VOD/Live TV/Radio) + Creator Channels + Auth + Wallet/Token dashboard
- Auth: Email/Password (JWT) + Emergent Google OAuth
- AI: recommendations + chatbot + summarization + subtitles + thumbnails
- Web3: simulated $LONO token (internal MongoDB ledger) — wallet, staking, watch-to-earn, DAO
- Payments: Stripe test key + simulated crypto/token purchase

## Personas
- Viewer/Listener — watches, listens, earns $LONO
- Creator — uploads, monetizes, simulcasts
- Investor / Token Holder — stakes, votes, tracks tokenomics
- Compliance Officer — reviews utility token disclosures

## Architecture (current)
- Backend: FastAPI + Motor (async MongoDB) + JWT + bcrypt + emergentintegrations (Claude Sonnet 4.5) + Stripe
- Frontend: React 19 + Tailwind + shadcn/ui + Recharts + sonner + framer-motion + lucide-react
- Fonts: Clash Display (headings) + Satoshi (body) via Fontshare
- All API routes prefixed with `/api`; frontend uses `REACT_APP_BACKEND_URL`

## Implemented (Feb 2026)
- Authentication: register/login (JWT), Emergent Google OAuth exchange, /auth/me
- Content: seeded 29 items across 8 kinds (movie, series, short, music, podcast, live_tv, live_radio, course), 6 channels, 4 governance proposals
- Home: Netflix-style hero + 9 rails (Featured, Trending, Top 10, Originals, New, Movies, Series, Podcasts, Music, Continue Watching when logged in)
- Watch page: video/audio player, AI Summary generator, similar content, watch-to-earn (1 LONO/min capped 10 per event), Whisper caption generator with in-player `<track>` element
- Live: /live shows Live TV & Live Radio grids with pulse indicators
- Browse: /browse/:kind category views
- Search: /search?q=
- Channel: /channel/:id with banner, avatar, uploads grid, subscribe CTA
- Creator Studio: auto-provisioned channel, stats (subscribers/views/revenue/LONO), 14-day chart, simulcast destinations panel (10 platforms), upload dialog with real file uploads (thumbnail + media, progress bar) to Emergent Object Storage
- Emergent Object Storage: `/api/storage/upload` (multipart, 100MB cap, MIME whitelist) → proxied `/api/files/{path}` playback URLs. `resolveMedia()` helper on frontend transparently prefixes backend origin.
- Whisper transcription: `/api/ai/transcribe/{content_id}` (verbose_json → VTT with segment timing), cached in Mongo, served via `/api/content/{id}/subtitles.vtt`.
- LoNo Wallet: total balance hero, available/staked/earned, stake dialog (30/90/180/365 days at 8-35% APY), unstake with pro-rata rewards, simulated $LONO purchase, Stripe premium upgrade, transactions table
- Tokenomics: supply metrics, 7-day price chart, allocation pie, treasury/creator/education/community funds
- Governance: 4 proposals, for/against/abstain voting weighted by balance+2×staked, one-vote enforcement
- AI Assistant: floating chat FAB (Claude Sonnet 4.5) with persistent session
- Sonner toasts for feedback across app

## Backlog (post-MVP priorities)
- **P0**: Real object storage for creator uploads (Emergent object storage playbook); AI transcription/subtitles via Whisper on watch page; real Stripe test key + webhook handling
- **P1**: LMS module (courses, quizzes, blockchain certificates), Learn-to-Earn tracking; Simulcast RTMP orchestration; Watch parties & multi-profile
- **P1**: Compliance dashboard (FCC/DMCA/KYC/AML/GDPR) — configurable modules per jurisdiction
- **P2**: Real blockchain settlement layer, WalletConnect / MetaMask integration
- **P2**: Marketplace (NFT, merch, tickets, licenses), programmatic ads platform, developer portal + SDK
- **P2**: SSO, biometric login, passkeys, 2FA

## Known Limitations
- Stripe key in env is placeholder `sk_test_emergent`; endpoint returns 500 until real test key set
- $LONO is a simulated internal ledger only (no on-chain settlement)
- Watch-to-Earn is triggered client-side after 20s viewing (server accepts arbitrary seconds — needs anti-abuse hardening for production)
