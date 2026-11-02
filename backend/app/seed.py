"""Demo catalogue (reused from the original build) plus Learn courses."""
import logging
import random
from datetime import timedelta

from .db import db
from .util import now, now_iso, uid

log = logging.getLogger("lono")

SEED_IMAGES = {
    "movie": [
        "https://images.unsplash.com/photo-1782020934325-cfe4cea4fd9c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwyfHxjaW5lbWF0aWMlMjBtb3ZpZSUyMHBvc3RlciUyMGRhcmt8ZW58MHx8fHwxNzgzMjUwNjQ4fDA&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1778585040075-0991abfd4ed9?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwzfHxjaW5lbWF0aWMlMjBtb3ZpZSUyMHBvc3RlciUyMGRhcmt8ZW58MHx8fHwxNzgzMjUwNjQ4fDA&ixlib=rb-4.1.0&q=85",
        "https://images.pexels.com/photos/3137890/pexels-photo-3137890.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    ],
    "live": [
        "https://images.pexels.com/photos/9072394/pexels-photo-9072394.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NzB8MHwxfHNlYXJjaHwyfHxsaXZlJTIwY29uY2VydCUyMHN0YWdlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDl8MA&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NzB8MHwxfHNlYXJjaHwxfHxsaXZlJTIwY29uY2VydCUyMHN0YWdlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDl8MA&ixlib=rb-4.1.0&q=85",
    ],
    "podcast": [
        "https://images.unsplash.com/photo-1655947717064-d856af599bd1?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxNzV8MHwxfHNlYXJjaHwxfHxwb2RjYXN0ZXIlMjBzdHVkaW8lMjBtaWNyb3Bob25lfGVufDB8fHx8MTc4MzI1MDY0OHww&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1636294155433-29863ca33aa6?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxNzV8MHwxfHNlYXJjaHwyfHxwb2RjYXN0ZXIlMjBzdHVkaW8lMjBtaWNyb3Bob25lfGVufDB8fHx8MTc4MzI1MDY0OHww&ixlib=rb-4.1.0&q=85",
    ],
    "abstract": [
        "https://images.unsplash.com/photo-1759771963975-8a4885446f1f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwyfHxhYnN0cmFjdCUyMG5ldHdvcmslMjBub2RlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDh8MA&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1737505599162-d9932323a889?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMG5ldHdvcmslMjBub2RlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDh8MA&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1775057154553-0f3e8902fea3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwzfHxhYnN0cmFjdCUyMG5ldHdvcmslMjBub2RlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDh8MA&ixlib=rb-4.1.0&q=85",
    ],
}

VIDEOS = [f"https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/{n}.mp4"
          for n in ("BigBuckBunny", "ElephantsDream", "Sintel", "TearsOfSteel", "ForBiggerBlazes")]
AUDIO = [f"https://www.soundhelix.com/examples/mp3/SoundHelix-Song-{n}.mp3" for n in range(1, 6)]

CHANNELS = [
    ("Aurora Studios", "@aurora", "Cinematic originals and documentaries.", 245000),
    ("Neon Beats", "@neon", "Late-night music and indie sessions.", 189000),
    ("Cortex Learning", "@cortex", "Deep-dive tech and science courses.", 412000),
    ("BroadWave Radio", "@broadwave", "24/7 talk, news and culture.", 76000),
    ("Solstice Cinema", "@solstice", "Sci-fi originals and short films.", 358000),
    ("Meridian Podcasts", "@meridian", "Long-form interviews and ideas.", 121000),
]


def _titles():
    return {
        "movie": [
            ("Midnight Static", "Drama", "A hacker's late-night discovery unravels a corporate empire."),
            ("Solar Flare", "Sci-Fi", "Astronauts race to prevent a catastrophic solar event."),
            ("The Cartographer", "Thriller", "A mapmaker inherits a chart to a hidden city."),
            ("Ember & Ash", "Drama", "Two sisters rebuild their lives after the fire."),
            ("Verdant Machine", "Sci-Fi", "Nature and AI collide in a lost Amazonian temple."),
            ("Nightingale Protocol", "Action", "A rogue agent breaks the silence."),
        ],
        "series": [
            ("Hollow Cities", "Drama", "Six strangers, one collapsing metropolis."),
            ("Quantum Diaries", "Sci-Fi", "Time-jumping researchers seek the anomaly."),
            ("The Broadcast", "Mystery", "A pirate radio show predicts real crimes."),
            ("Aurora Kids", "Family", "A whimsical adventure for young explorers."),
        ],
        "podcast": [
            ("Signal Path", "Tech", "Conversations at the edge of software and life."),
            ("Deep Focus", "Business", "Founders on building at scale."),
            ("Studio Sessions", "Music", "Musicians dissect their creative process."),
            ("Meridian Notes", "Culture", "Long-form ideas from the world's best thinkers."),
        ],
        "music": [
            ("After Hours EP", "Electronic", "A moody electronic set for late-night hours."),
            ("Solstice", "Ambient", "Ambient textures for focused work."),
            ("Neon Highway", "Synthwave", "Drive fast, feel the neon."),
            ("Analog Church", "Indie", "Warm indie recorded to tape."),
        ],
        "short": [
            ("60 Seconds in Tokyo", "Travel", "A minute of neon-drenched Shibuya."),
            ("Studio Cut", "Behind the Scenes", "Inside a director's edit bay."),
        ],
        "course": [
            ("Foundations of Web3", "Education", "Tokens, wallets and DAOs explained without the jargon."),
            ("AI for Creators", "Education", "Practical AI tools for creators and studios."),
        ],
        "live_tv": [
            ("LoNo News 24", "News", "Rolling world news around the clock."),
            ("Culture Live", "Culture", "Interviews, performances, and events."),
            ("Sports Central", "Sports", "Live commentary and analysis."),
            ("Cinema Classics", "Movies", "Curated classic cinema, all day."),
        ],
        "live_radio": [
            ("BroadWave 101", "Talk", "Talk radio for curious minds."),
            ("Neon FM", "Music", "Non-stop synthwave and indie."),
            ("Meridian Voices", "Interview", "Long-form interviews on air."),
        ],
    }

async def seed_catalogue():
    if await db.content.count_documents({}) > 0:
        return
    log.info("Seeding demo catalogue")
    rng = random.Random(7)
    channels = []
    for i, (name, handle, bio, subs) in enumerate(CHANNELS):
        channels.append({"id": uid(), "owner_id": "system", "name": name, "handle": handle,
                         "banner_url": SEED_IMAGES["abstract"][i % 3],
                         "avatar_url": f"https://api.dicebear.com/7.x/shapes/svg?seed={handle}",
                         "bio": bio, "subscribers": subs, "created_at": now_iso()})
    await db.channels.insert_many([dict(c) for c in channels])
    cortex = next(c for c in channels if c["handle"] == "@cortex")

    docs = []
    for kind, entries in _titles().items():
        for title, cat, desc in entries:
            pool = (SEED_IMAGES["live"] if kind in ("live_tv", "live_radio") else
                    SEED_IMAGES["podcast"] if kind == "podcast" else
                    SEED_IMAGES["abstract"] if kind in ("music", "course") else SEED_IMAGES["movie"])
            audio = kind in ("music", "podcast", "live_radio")
            docs.append({
                "id": uid(), "title": title, "description": desc, "kind": kind, "category": cat,
                "thumbnail_url": rng.choice(pool),
                "stream_url": rng.choice(AUDIO) if audio else rng.choice(VIDEOS),
                "duration_sec": 0 if kind.startswith("live") else rng.randint(600, 7200),
                "is_original": rng.random() > 0.5, "is_premium": rng.random() > 0.7,
                "channel_id": cortex["id"] if kind == "course" else rng.choice(channels)["id"],
                "views": rng.randint(1000, 950000), "likes": rng.randint(100, 45000),
                "rating": round(rng.uniform(3.5, 4.9), 1), "year": rng.randint(2020, 2026),
                "created_at": (now() - timedelta(days=rng.randint(0, 90))).isoformat(),
            })
    await db.content.insert_many(docs)

    t = now()
    await db.proposals.insert_many([
        {"id": uid(), "title": "Increase Creator Fund by 25M $LONO",
         "summary": "Expand grants for emerging creators focused on documentary and educational content.",
         "status": "active", "votes": {"for": 1240000, "against": 210000, "abstain": 45000},
         "ends_at": (t + timedelta(days=5)).isoformat(), "created_at": now_iso()},
        {"id": uid(), "title": "Double Learn-to-Earn rewards next quarter",
         "summary": "Double $LONO rewards for passing course quizzes for the next quarter.",
         "status": "active", "votes": {"for": 890000, "against": 175000, "abstain": 30000},
         "ends_at": (t + timedelta(days=12)).isoformat(), "created_at": now_iso()},
        {"id": uid(), "title": "Launch a community-curated Live TV channel",
         "summary": "Let token holders programme a 24/7 live channel by weekly vote.",
         "status": "active", "votes": {"for": 512000, "against": 420000, "abstain": 60000},
         "ends_at": (t + timedelta(days=8)).isoformat(), "created_at": now_iso()},
        {"id": uid(), "title": "Burn 5M $LONO from the treasury",
         "summary": "Reduce circulating supply to strengthen network economics.",
         "status": "passed", "votes": {"for": 2100000, "against": 320000, "abstain": 80000},
         "ends_at": (t - timedelta(days=3)).isoformat(), "created_at": now_iso()},
    ])
    log.info("Seeded %d titles, %d channels", len(docs), len(channels))


def _q(prompt, options, answer, why):
    return {"id": uid(), "prompt": prompt, "options": options, "answer_index": answer, "explanation": why}


def _l(title, body, video=None, minutes=6):
    return {"id": uid(), "title": title, "body": body.strip(), "video_url": video, "duration_sec": minutes * 60}


COURSES = [
    {
        "title": "Foundations of Web3", "level": "Beginner", "reward_lono": 25,
        "description": "Tokens, wallets and DAOs explained without the jargon, using LoNo's own token as the worked example.",
        "lessons": [
            _l("What a token is", """
A token is an entry in a shared ledger that says who holds how much of something. On a public blockchain that ledger is copied across thousands of computers, so no single company can quietly change it.

$LONO on this platform is a simulated utility token: the ledger lives in LoNo's own database. It behaves like a real token inside the app (you can earn, stake and vote with it) but it has no cash value and can't be withdrawn."""),
            _l("Wallets and addresses", """
A wallet doesn't hold tokens; it holds the keys that prove a ledger entry is yours. Your address is the public label others use to send to you, like an account number.

Your LoNo wallet address starts with lono1. Because $LONO is simulated, LoNo manages the keys for you. With a self-custody wallet such as MetaMask, losing your recovery phrase means losing access for good."""),
            _l("Staking and yield", """
Staking means locking tokens for a fixed period in return for a reward, usually quoted as APY (annual percentage yield). Longer locks earn more because your tokens are unavailable for longer.

On LoNo you can lock for 30, 90, 180 or 365 days at 8, 14, 22 or 35% APY. If you unstake early you get your tokens back but give up the reward."""),
            _l("DAOs and voting", """
A DAO (decentralised autonomous organisation) is a group that makes decisions by token-weighted vote rather than by a management team.

In LoNo's DAO your voting power is your available balance plus twice your staked balance, which rewards long-term commitment. Each account gets one vote per proposal, and you need at least 100 staked $LONO to submit a proposal of your own."""),
        ],
        "quiz": [
            _q("What is $LONO on this platform?", ["A cryptocurrency you can cash out", "A simulated utility token on LoNo's own ledger", "A loyalty card", "A stablecoin pegged to the dollar"], 1, "$LONO is tracked in LoNo's database and has no cash value."),
            _q("What does a wallet actually hold?", ["The tokens themselves", "A copy of the blockchain", "The keys that prove ownership", "Your email address"], 2, "Tokens live on the ledger; the wallet holds the keys."),
            _q("What happens if you unstake before the lock ends?", ["You lose your tokens", "You get your tokens back but no reward", "You pay a 50% fee", "Nothing changes"], 1, "Principal is returned; the reward is forfeited."),
            _q("How is voting power calculated in LoNo's DAO?", ["One account, one vote", "Balance plus twice the staked amount", "Staked amount only", "Total earned all time"], 1, "Staked tokens count double to reward commitment."),
        ],
    },
    {
        "title": "AI for Creators", "level": "Intermediate", "reward_lono": 30,
        "description": "Use AI to caption, summarise and package your shows, and know where human judgement still matters.",
        "lessons": [
            _l("Captions that reach more people", """
Captions make content usable for deaf and hard-of-hearing viewers, for people watching on mute, and for search engines. Speech-to-text models such as Whisper produce timed transcripts that become a WebVTT caption file.

Always review automatic captions for names, jargon and anything said over music. One wrong word in a name can undo the trust a caption builds."""),
            _l("Summaries and metadata", """
A good synopsis tells viewers what kind of experience they're choosing, not every plot point. AI can draft one from your description or transcript in seconds.

Use AI drafts as a starting point. Check tone, remove spoilers and make sure tags describe the content honestly; misleading tags hurt recommendations later."""),
            _l("Prompting well", """
Clear prompts get usable drafts. State the audience, the length, the format and one or two examples of what good looks like.

"Write a 3-sentence, spoiler-free synopsis for a family audience, then 5 tags" works far better than "describe my video"."""),
            _l("Rights and disclosure", """
Only feed AI tools material you have the rights to use, and check each tool's terms on how your uploads are stored or reused.

If a voice, face or likeness is AI-generated, say so. Audiences forgive tools; they don't forgive being misled."""),
        ],
        "quiz": [
            _q("Why review automatic captions?", ["They're always wrong", "Names, jargon and music-heavy passages are often misheard", "Platforms require it", "To make files smaller"], 1, "Speech-to-text struggles most with proper nouns and noisy audio."),
            _q("What makes a good synopsis?", ["Every plot twist", "A clear sense of the experience without spoilers", "As many keywords as possible", "Exactly one sentence"], 1, "Viewers want to know what they're choosing, not the ending."),
            _q("Which prompt will give a more usable draft?", ["\"Describe my video\"", "\"3-sentence, spoiler-free synopsis for a family audience, then 5 tags\""], 1, "Audience, length and format make the difference."),
            _q("When should you disclose AI use?", ["Never", "When a voice, face or likeness is AI-generated", "Only for music", "Only if asked"], 1, "Disclose synthetic likenesses so audiences aren't misled."),
        ],
    },
    {
        "title": "Broadcasting 101: Radio to Streaming", "level": "Beginner", "reward_lono": 20,
        "description": "How a signal gets from a studio to a listener, from FM transmitters to live streams and podcasts.",
        "lessons": [
            _l("How radio reaches you", """
An FM or AM station turns audio into a radio wave from a transmitter. Anyone with a receiver in range can listen, with no data plan and no account, which is why radio is still the most reliable mass medium in many countries, especially during emergencies."""),
            _l("From broadcast to streaming", """
Streaming sends audio or video as data over the internet. It reaches anyone online, anywhere, and lets viewers pause, rewind and pick what to watch, but it depends on connectivity and costs data.

Many stations now simulcast: the same programme goes out over the air and as a live stream at once."""),
            _l("Live versus on-demand", """
Live content happens now: news, sport, call-in shows. On-demand (VOD for video, AOD for audio) is recorded and available any time, like films and podcasts.

Live builds community and urgency; on-demand builds a library that keeps earning views. Strong channels do both, clipping live shows into on-demand highlights."""),
            _l("Licensing and rules", """
Broadcasting over the air usually needs a licence from the national regulator, and every channel must respect copyright for music and footage it plays.

Online platforms also handle takedown requests and age ratings. Keep records of the rights you hold for everything you publish."""),
        ],
        "quiz": [
            _q("Why is radio still important in many places?", ["It's newer than streaming", "It reaches anyone in range with no data or account", "It has better sound", "It's free to run"], 1, "Radio needs only a receiver, which matters most in emergencies."),
            _q("What is simulcasting?", ["Playing two songs at once", "Sending the same programme over the air and as a stream", "Recording a podcast", "Broadcasting in two languages"], 1, "Same programme, two delivery routes, same time."),
            _q("Which is an example of on-demand content?", ["A live football match", "A breaking news bulletin", "A podcast episode", "A call-in show"], 2, "On-demand content is recorded and available any time."),
            _q("What do you need to play someone else's music on air?", ["Nothing", "The right licences", "A large audience", "A streaming account"], 1, "Copyright applies to everything you broadcast."),
        ],
    },
]


async def seed_courses():
    if await db.courses.count_documents({}) > 0:
        return
    cortex = await db.channels.find_one({"handle": "@cortex"}) or {}
    for i, spec in enumerate(COURSES):
        item = await db.content.find_one({"kind": "course", "title": spec["title"]})
        if not item:
            item = {"id": uid(), "title": spec["title"], "description": spec["description"], "kind": "course",
                    "category": "Education", "thumbnail_url": SEED_IMAGES["abstract"][i % 3],
                    "stream_url": VIDEOS[i % len(VIDEOS)], "duration_sec": 1800, "is_original": True,
                    "is_premium": False, "channel_id": cortex.get("id"), "views": 0, "likes": 0,
                    "rating": 4.7, "year": now().year, "created_at": now_iso()}
            await db.content.insert_one(dict(item))
        lessons = [dict(l, video_url=l["video_url"] or item["stream_url"]) for l in spec["lessons"]]
        await db.courses.insert_one({
            "id": uid(), "content_id": item["id"], "title": spec["title"], "description": spec["description"],
            "level": spec["level"], "reward_lono": spec["reward_lono"], "thumbnail_url": item["thumbnail_url"],
            "channel_id": item.get("channel_id"), "lessons": lessons, "enrolled": 0,
            "quiz": {"pass_mark": 0.75, "questions": spec["quiz"]}, "created_at": now_iso()})
    log.info("Seeded %d courses", len(COURSES))
