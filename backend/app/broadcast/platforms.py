"""Simulcast destinations. This is the list shown in Creator Studio before this
release (10 tiles), with how each can actually be reached. LoNo connects by
server URL + stream key, the method OBS and other encoders use; platform
sign-in (OAuth) would need LoNo to be an approved app with each platform."""

PLATFORMS = [
    {"id": "youtube", "name": "YouTube Live", "supported": True, "protocols": ["rtmp", "rtmps"],
     "default_url": "rtmps://a.rtmps.youtube.com/live2",
     "where": "YouTube Studio → Go live → Stream → Stream key and Stream URL."},
    {"id": "facebook", "name": "Facebook Live", "supported": True, "protocols": ["rtmps"],
     "default_url": "rtmps://live-api-s.facebook.com:443/rtmp/",
     "where": "Facebook → Live video → Streaming software → Server URL and Stream key. Facebook accepts RTMPS only."},
    {"id": "twitch", "name": "Twitch", "supported": True, "protocols": ["rtmp", "rtmps"],
     "default_url": "rtmp://live.twitch.tv/app",
     "where": "Twitch Creator Dashboard → Settings → Stream → Primary Stream key."},
    {"id": "kick", "name": "Kick", "supported": True, "protocols": ["rtmps"], "default_url": "",
     "where": "Kick dashboard → Settings → Stream URL & Key. Paste both."},
    {"id": "x", "name": "X Live", "supported": True, "protocols": ["rtmp", "rtmps"], "default_url": "",
     "where": "X Media Studio → Producer → Sources → create an RTMP source. Requires an account with Producer access."},
    {"id": "tiktok", "name": "TikTok Live", "supported": True, "protocols": ["rtmp"], "default_url": "",
     "where": "TikTok LIVE Center / LIVE Studio → stream key. Only eligible accounts are given a server URL and key."},
    {"id": "linkedin", "name": "LinkedIn Live", "supported": True, "protocols": ["rtmps"], "default_url": "",
     "where": "LinkedIn → Create a live event → Custom stream → Stream URL and Stream key. Requires LinkedIn Live access."},
    {"id": "instagram", "name": "Instagram Live", "supported": True, "protocols": ["rtmps"], "default_url": "",
     "where": "Instagram (professional account) → Live Producer → Stream URL and Stream key. Keys are valid for one broadcast."},
    {"id": "discord", "name": "Discord", "supported": False, "protocols": [], "default_url": "",
     "where": "Discord has no stream-key ingest, so LoNo can't send a broadcast to it. Share the LoNo link in your server instead."},
    {"id": "custom", "name": "Custom RTMP / RTMPS / SRT", "supported": True, "protocols": ["rtmp", "rtmps", "srt"],
     "default_url": "", "where": "Any server that accepts RTMP, RTMPS or SRT: another platform, a CDN or your own server."},
]
BY_ID = {p["id"]: p for p in PLATFORMS}


def target_url(server_url: str, key: str) -> str:
    """Join server URL and stream key the way encoders do."""
    if server_url.startswith("srt://"):
        sep = "&" if "?" in server_url else "?"
        return f"{server_url}{sep}streamid={key}" if key else server_url
    return server_url.rstrip("/") + "/" + key if key else server_url
