# Running a paid replay-pass campaign (pilot)

The pilot campaign: **one football match, one organizer, one paying sponsor, and one limited offer of replay passes.**
- **Fans** earn $LONO by watching on LoNo and redeem it for a pass.
- **The sponsor** pays LoNo in ordinary currency.
- **LoNo** pays the organizer and keeps a campaign fee.

The same steps work later for other broadcasters, events and CIU short courses: the replay can be any title hosted on LoNo, and the earning activity any title fans watch.

**Success test:** the sponsor pays, fans use their passes, the organizer is paid, and LoNo covers its direct costs. **A second paid booking is the signal to expand.**

## Before the first campaign (one-time)

- **Pilot mode.** Run LoNo with `PILOT_MODE=true` (in `backend/.env`, or as an environment setting in Docker). In pilot mode:
  - $LONO is **earned, redeemable and non-transferable**: there's no buying, no signup bonus, and no new staking.
  - Existing stakes stop earning rewards from the pilot start date. Their principal, and rewards earned up to then, are still paid out.
  - Course creators are paid in currency, not $LONO.
  - Balances and history are untouched.
- **Staff accounts.** Campaign staff need admin access: add their emails to `ADMIN_EMAILS`. Every staff action is recorded with their name.
- **HTTPS and a public address.** Fans on phones need LoNo on an https address.
- **Database.** Use a real MongoDB (Docker mode includes one), not the in-memory demo database.

## 1. Agree the deal (outside LoNo)

Write down and get signed:

| Item | Example |
|---|---|
| Sponsor and organizer | Lone Star Cell; County FA |
| What fans get | A pass to the full-match replay for 7 days |
| Passes | 500 |
| Claim window | From kick-off + 3 h to 7 days later |
| Points price, and how fans earn them | 30 $LONO; watch 2 minutes of the match preview (worth 30 $LONO) |
| Sponsor pays LoNo | e.g. USD 500, invoiced |
| LoNo pays the organizer | e.g. USD 300 after the claim window |
| LoNo fee | e.g. USD 150 |
| Direct costs | e.g. USD 50: delivery, support |
| Distribution permission | The organizer's written permission for LoNo to show the replay to pass holders |

Keep the sums consistent: **sponsor payment = organizer payment + LoNo fee + direct costs.** The report shows any gap as "fee variance".

**Earning rule:** keep it clear and achievable, about 2 to 3 minutes of watching. Fans also earn the normal watch rewards anywhere on LoNo, so they can earn on one channel and spend on another organizer's offer.

## 2. Get the video onto LoNo

The organizer, or staff, uploads **two titles** through **Creator Studio → Upload**:

- **The preview** (public): the earning activity.
- **The replay**: it must be **uploaded to LoNo**, so LoNo can protect its delivery. An external link can't be protected and is refused. Use H.264 video with AAC audio in MP4, which plays on all phones.

**When the replay is attached to a campaign, LoNo locks it:**
- Its file can no longer be opened directly.
- Its page shows "This replay needs a pass".
- It only plays from **My passes**, for the fan who claimed it.

## 3. Create the campaign (draft)

**Admin → Campaigns → New campaign**:

1. **Add the sponsor and organizer** (Add partner), then select them.
2. **Fill in the offer:**
   - **Title fans see:** for example "County Final: full-match replay".
   - **Replay and earning activity:** search and pick both titles.
   - **Earning rule:** minutes to watch and $LONO earned.
   - **The pass:** price, number of passes, opening time, claim deadline, access days, and the report window (14 days is a good default).
3. **Money:** currency, sponsor payment, organizer payment, LoNo fee and direct costs. These are **records of ordinary money**, kept separate from $LONO.
4. **Create draft.** Fans can't see drafts.

## 4. Confirm, then open

The offer can **only open after all three are confirmed**; until then the **Open offer** button stays disabled.

| Confirmation | What staff record |
|---|---|
| **Sponsor payment received** | The payment or bank reference, and the amount received, which must be at least the agreed amount. Invoice the sponsor outside LoNo first |
| **Distribution permission** | The agreement or permission reference |
| **Playback ready** | Press **Check playback and confirm**. LoNo checks for itself that the replay is hosted, protected and present in storage |

Then press **Open offer**.

**Before telling fans, rehearse:**
- In a private window, sign up as a test fan, watch the preview, claim a pass on a phone and play the replay.
- **Reverse that test claim** afterwards (see below), so it doesn't count.

## 5. While the offer runs

- **Fans** see the offer under **Offers**: sponsor, price, passes left, claim deadline and how long they can watch. Before spending, they confirm.
- **The replay** is then in **My passes**, and plays on phones.
- **One pass per fan.** A double tap or a retry on a bad connection never charges twice. When passes run out, the remaining fans are told, and **their points are not taken.**
- **Pause new claims** if something is wrong: existing passes keep working. **Resume** when it's fixed.
- **Close campaign** at the end, or earlier if needed. No new claims are accepted; claimed passes keep their full access period.

## 6. Reverse a failed or canceled redemption

**Campaigns → (campaign) → Claims → Reverse.** Give a reason. LoNo:
- **restores the fan's points exactly once:** pressing it twice does nothing more
- **returns the pass to inventory only if the offer is still open.** You can choose not to return it, for example if the fan already watched
- **stops that pass's replay access immediately**
- records who reversed it, and why

## 7. Settle

1. Pay the organizer **outside LoNo** after the claim window. Then record it under **Settlement**: amount and payment reference.
2. Record the **sponsor invoice reference**, and the **actual direct costs** if they differ.
3. Check **Reconciliation** in the report. Every line should show ✓:
   - **Points:** points debited minus refunds equals price × active passes.
   - **Inventory:** the pass counter matches active passes, plus reversed passes kept out of inventory.
   - **Earning bonus:** bonuses awarded match the ledger.
   - **Cash:** the sponsor payment was received, and the organizer was paid as agreed.

   A ✗ means a record needs attention before you report to the sponsor.

## 8. Report and ask for the next booking

**The staff report:**
- passes available, claimed and left; reversals
- unique replay viewers, and the share of passes actually watched
- **repeat viewers** within the report window
- watch minutes
- sponsor payment, organizer settlement, direct costs, and **contribution after direct costs**

**The sponsor report** (**Sponsor report (CSV)**) contains aggregate figures only, with no fan names, emails or money:
- passes offered and claimed
- **fans who actually watched** the replay, as distinct from those who only claimed
- fans who came back
- watch minutes
- fans who earned points

**Did they book again?** Record whether the sponsor and organizer booked another campaign, and update it when you know.

## Quick troubleshooting

| Problem | What to do |
|---|---|
| "Can't open yet. Missing: …" | Record the missing confirmation |
| "Playback isn't ready: …" | The replay must be uploaded to LoNo. Check the file finished uploading |
| A fan says "All passes have been claimed" | Their points weren't used. Add passes (edit **Passes available**) if the sponsor agrees |
| A fan can't play on a shared link | By design: passes play only from that fan's **My passes** |
| A pass's replay stopped working | Check the claim wasn't reversed, and the access period hasn't ended |
| Reconciliation shows a claim still processing | LoNo finishes or undoes interrupted claims automatically within about two minutes |

## Limits of the pilot

- **Money isn't processed by LoNo:** invoicing and payouts happen outside the app and are recorded here.
- **Protected playback** requires the replay to be stored on LoNo. With S3 storage, files are handed over as short-lived signed links, valid for about a minute.
- **Pass links** are tied to the fan's browser session. A fan who shares their whole signed-in device shares their access.
- **Account farming:** fans could try to earn with several accounts. The signup bonus is off and sign-ups are rate-limited per network, but watch the report for unusual claim patterns.

## Staging rehearsal (Nov 2026)

`scripts/pilot/rehearsal.py`, run against LoNo in pilot mode on a **real MongoDB 7.0** server, using a test sponsor, organizer and replay.

**Result: 27 of 27 checks passed**, with no browser errors:
- **Setup:** pilot mode on (no purchases, no signup bonus). The organizer uploaded the preview and replay through the creator workflow. Staff created the campaign in the admin console.
- **Opening rules:**
  - **an unfunded campaign couldn't be opened** (button disabled; the API refused)
  - fans couldn't see the draft
  - the offer opened after the three confirmations, with every change recorded by name
- **The fan on a phone** (iPhone 13 profile):
  - saw sponsor, price, passes left, claim deadline and access period
  - **earned 30 $LONO by watching the preview**
  - confirmed and **claimed, then watched the replay on the phone**
  - found it in My passes
  - five simultaneous retries returned the same claim, with one deduction
- **The last pass:** 12 more fans earned points through the same rule. **11 fans claimed the last pass within 0.06 s: exactly one won**, and the other 10 got "all claimed" and kept their points. Inventory never went below zero.
- **Unauthorized viewers:**
  - **a shared playback URL returned 403** in another browser, anonymously, and for a signed-in fan without a pass, who saw "needs a pass"
  - the replay file returned 403 when fetched directly
- **Reversal:** a redemption reversed twice restored points once, and returned the pass while the offer was open.
- **Settlement and reports:**
  - settlement and rebooking recorded
  - **the report reconciled with the points ledger and the cash records** (contribution 150 after direct costs)
  - every fan's balance equalled the sum of their ledger entries
  - the sponsor report separated 2 claimed passes from 1 actual view; the CSV contained no money
- **Pause and close:** both stopped new claims, while existing passes kept working.

**Existing workflows, through their normal entry points, against the same pilot-mode staging:**
- learner flow, course builder, reviews and settings
- device and HLS playback
- TV remote (31 of 31)

All passed.

**Not tested here:**
- real phones (only Chromium with phone profiles)
- H.264 replays (the sandbox browser can't decode H.264, so VP9 test files were used)
- S3 storage
- real sponsor payments or bank transfers (references were recorded as text)
