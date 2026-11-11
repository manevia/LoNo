# LoNo on Cloudflare (https://lono.ciu.edu.lr)

LoNo runs on your Cloudflare account, with no server of your own:

| Part | Cloudflare service |
|---|---|
| The website | Workers static assets |
| The API (LoNo's Python backend) | One always-on **Container**, reached through a Worker |
| Videos, replays, uploads | **R2** (no charge when viewers download) |
| HTTPS and the `lono.ciu.edu.lr` address | Your `ciu.edu.lr` domain in Cloudflare |
| Database | **MongoDB Atlas** (MongoDB's managed cloud service; Cloudflare has no MongoDB) |

**This is stage 1.** It runs the website, accounts, courses, on-demand video and the commercial pilot (replay passes). **Live broadcasting and the Live Control Room are off** in this setup; stage 2 moves them to Cloudflare Stream.

Deployment runs from GitHub, so there's nothing to install on your computer. It takes about 30 minutes the first time.

## 1. MongoDB Atlas (the database)

1. **Sign up** at **mongodb.com/atlas**.
2. **Create a cluster.** **Flex** or **M0 (free)** is enough for the pilot. Pick a cloud region in **Europe** (for example AWS Frankfurt or Ireland).
3. **Database Access → Add New Database User:**
   - Username: `lono`
   - **Autogenerate** a strong password, and copy it
   - Built-in role: **Read and write to any database**
4. **Network Access → Add IP Address → Allow access from anywhere** (`0.0.0.0/0`).
   - Why: Cloudflare Containers don't have fixed addresses, so Atlas can't be limited to them.
   - What still protects the data: the strong password, Atlas's mandatory encryption, and a user that can only read and write data.
5. **Database → Connect → Drivers** (Python), then copy the connection string. It looks like `mongodb+srv://lono:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority`. Put the real password in place of `<password>`. This is your **MONGO_URL**.

## 2. Cloudflare

1. **Plan:** in **Workers & Pages → Plans**, choose **Workers Paid**. Containers require it.
2. **R2:** open **R2** in the dashboard once to enable it (you may be asked to confirm billing details). Then **R2 → Manage API tokens → Create API token**:
   - Permissions: **Object Read & Write**
   - Specify bucket: **lono-media** (if the bucket doesn't exist yet, choose "Apply to all buckets"; the deploy creates `lono-media`)
   - Copy the **Access Key ID** and **Secret Access Key**: these are **R2_ACCESS_KEY_ID** and **R2_SECRET_ACCESS_KEY**
3. **Account ID:** shown on the right of the account's **Workers & Pages** overview. This is **CLOUDFLARE_ACCOUNT_ID**.
4. **Deploy token:** **My Profile → API Tokens → Create Token**, starting from the **"Edit Cloudflare Workers"** template. Add:
   - **Account → Containers → Edit**
   - **Account → Workers R2 Storage → Edit** (if the template doesn't include it)
   - **Zone → DNS → Edit**, for **ciu.edu.lr** (to create the `lono` address)
   - Under **Zone Resources**, select **ciu.edu.lr**

   Create it and copy it. This is **CLOUDFLARE_API_TOKEN**.
5. **Don't create a `lono` DNS record yourself.** The deployment adds `lono.ciu.edu.lr` as the Worker's custom domain, and Cloudflare creates the record. **If you or Cloudflare's assistant already created a `lono` record, delete it first**; an existing record blocks the custom domain.

## 3. GitHub

In **github.com/manevia/LoNo → Settings → Secrets and variables → Actions → New repository secret**, add:

| Name | Value |
|---|---|
| `CLOUDFLARE_API_TOKEN` | the deploy token (2.4) |
| `CLOUDFLARE_ACCOUNT_ID` | the account ID (2.3) |
| `MONGO_URL` | the Atlas connection string (1.5) |
| `R2_ACCESS_KEY_ID` | from the R2 API token (2.2) |
| `R2_SECRET_ACCESS_KEY` | from the R2 API token (2.2) |
| `ADMIN_PASSWORD` | the password you want for **msf@ciu.edu.lr** (used only when the admin account is first created) |

Optional: `ANTHROPIC_API_KEY` (AI assistant), `GOOGLE_CLIENT_ID` (Google sign-in).

You don't create LoNo's internal secrets (sign-in signing and key encryption). The first deployment generates them in Cloudflare, and later deployments leave them unchanged.

## 4. Deploy

**Actions → Deploy to Cloudflare → Run workflow.** It:
1. Checks the secrets above, and names any that are missing.
2. Builds the website.
3. Creates the **lono-media** R2 bucket and its upload rules: uploads and playback are allowed only from `https://lono.ciu.edu.lr`.
4. Builds the API container and deploys everything.
5. Waits until **https://lono.ciu.edu.lr** answers.

The first run takes **10 to 20 minutes** (building and placing the container); later runs are quicker. Run it again whenever you want the latest version on GitHub live.

## 5. Check

1. **Open https://lono.ciu.edu.lr** and sign in as **msf@ciu.edu.lr** with your `ADMIN_PASSWORD`.
2. **Open https://lono.ciu.edu.lr/api/admin/request-info:**
   - `scheme` should be **https**
   - `client_ip` should be **your own public IP**
3. **Creator Studio → Upload** a short video. The progress bar runs as the file goes straight to R2. The video should then play.
4. **For the pilot,** follow **[PILOT-OPERATOR-GUIDE.md](PILOT-OPERATOR-GUIDE.md)**. Pilot mode is on in this setup.

## Everyday

- **Updating:** rerun the workflow.
- **Logs:** **Workers & Pages → lono → Logs**; the API's messages are under the container.
- **Settings** such as the admin email and pilot mode are in `cloudflare/wrangler.jsonc` (`vars`). Change them on GitHub, then rerun the workflow.
- **Backups:**
  - **The database:** Atlas takes snapshots on paid tiers. On **M0 (free)**, export regularly with Atlas's tools, or move to Flex or a dedicated tier before real money flows.
  - **The videos:** they live in R2, which is replicated by Cloudflare.

## How it works, and its limits

- **Routing:** the Worker serves the website from Cloudflare's network, and sends `/api` to the API container.
  - It replaces any client-supplied forwarding header with Cloudflare's `CF-Connecting-IP`, so LoNo's per-visitor limits see real visitors and can't be spoofed.
  - The service worker and app shell are never cached; built files are cached for a year.
- **Uploads go straight from the browser to R2,** with a signed address that's valid once, then LoNo confirms the size. This avoids Cloudflare's 100 MB request limit; files up to 4 GB work.
- **Replays and other protected videos:** LoNo checks the pass and the fan's cookie, then hands out a **2-minute** signed R2 link.
- **The API runs as one instance** (`max_instances: 1`). A cron ping every 5 minutes keeps it awake, so background jobs, such as repairing interrupted pass claims, keep running. If it ever restarts, the first request waits a few seconds.
- **Off in stage 1:** live broadcasting, simulcast and the Live Control Room. Cloudflare Containers can't receive RTMP, SRT or WebRTC from encoders and cameras; stage 2 uses Cloudflare Stream for that.

## How this was tested

The deployment itself couldn't be run from the development sandbox (no access to your Cloudflare account or to Cloudflare's API). These parts were tested:

- **Storage:**
  - **Direct uploads, signed links and protected replays** against an S3-compatible test server, using the same API calls as R2. Upload, size check, seeking, refusal of the plain file address and of a shared link without the fan's cookie, and the 2-minute replay link: all pass.
  - **The browser path:** a real Studio upload went **straight from the browser to storage**, with CORS rules identical to `r2-cors.json`, and the video then played through LoNo.
- **The Worker:**
  - it type-checks
  - Wrangler 4.154 validated the configuration (assets, Durable Object, container, cron, settings)
  - run locally in Cloudflare's runtime, website pages and app routes were served from assets, with the cache headers above, and `/api` was routed to the API path
- **The secrets helper** generates internal secrets only when missing, and prints names only.

**Not tested:**
- **The deployment on Cloudflare:** the container build and placement, the custom domain, R2's real endpoint, and the token permissions.
- **MongoDB Atlas.**

The first workflow run is the real test. If it fails, the step's message says what to fix.
