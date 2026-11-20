# LoNo on CIU Coolify

Deploy the public Git repository using Docker Compose and `/docker-compose.coolify.yml` at https://deploy.ciu.edu.lr/. Assign the HTTPS domain only to the web service on port 80. Coolify's proxy handles TLS. The stack provisions authenticated MongoDB and persistent database and media volumes. Coolify generates the `SERVICE_PASSWORD_*` values; preserve them across redeployments.

Start on a temporary domain with `PUBLIC_ORIGIN` set to that HTTPS origin. Keep `MEDIA_ENABLED=false` until the media ingress DNS name, available host ports, TLS, and external connectivity are verified. Before switching the existing domain, inventory and migrate any existing Atlas data and preserve or explicitly rotate existing signing and encryption secrets. Keep the existing Worker until cutover is verified.

For R2, set `STORAGE_BACKEND=s3`, `S3_ENDPOINT_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in Coolify and allow the chosen origin in the R2 CORS rules. Verify upload and playback before enabling paid campaigns. Configure both Stripe settings before opening checkout.

For browser-camera ingest, the Coolify stack advertises `lono.ciu.edu.lr` and uses port 18189 for encrypted WebRTC media over UDP with TCP fallback. Allow these two transports only after checking the host's available ports and confirming the public exposure. Set `MEDIA_ENABLED=true` after verifying connectivity and test a private broadcast. The WHIP/WHEP signaling stays on HTTPS through the existing web service. OBS ingest requires a separate RTMPS configuration and certificate. Keep MongoDB and internal MediaMTX control ports private. Configure and test backups and restore before accepting real customer data.
