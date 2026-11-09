// Plain-language terms, $LONO disclosure and privacy summary.
// OPERATOR NOTE: this is a starting template. Have it reviewed by a lawyer for the
// countries you operate in before launch, then bump TERMS_VERSION on the server so
// existing users are asked to accept the new version.
import { Link } from "react-router-dom";
import { useConfig } from "@/lib/config";

const H = ({ id, children }) => <h2 id={id} className="mt-12 font-display text-2xl tracking-tight scroll-mt-24">{children}</h2>;
const P = ({ children }) => <p className="mt-4 text-gray-300 leading-relaxed">{children}</p>;
const L = ({ children }) => <ul className="mt-4 space-y-2 text-gray-300 leading-relaxed list-disc pl-6">{children}</ul>;

export default function Terms() {
  const cfg = useConfig();
  const contact = cfg.support_email
    ? <a href={`mailto:${cfg.support_email}`} className="text-white underline">{cfg.support_email}</a>
    : "LoNo support";

  return (
    <div data-testid="terms-page" className="max-w-[72ch] mx-auto px-4 md:px-8 pt-10 pb-32">
      <h1 className="font-display text-4xl md:text-5xl font-semibold tracking-tighter">Terms and $LONO disclosure</h1>
      <p className="mt-3 text-sm text-gray-400">Version {cfg.terms_version || "2026-11"}. We'll ask you to accept again if this changes.</p>

      <nav aria-label="On this page" className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <a href="#lono" className="text-[#FFB000] hover:underline">$LONO is not money</a>
        <a href="#using" className="text-gray-300 hover:text-white">Using LoNo</a>
        <a href="#creators" className="text-gray-300 hover:text-white">Creators</a>
        <a href="#privacy" className="text-gray-300 hover:text-white">Your data</a>
        <a href="#changes" className="text-gray-300 hover:text-white">Changes and contact</a>
      </nav>

      <section id="lono" className="mt-10 p-6 rounded-2xl border border-[#FFB000]/30 bg-[#FFB000]/[0.06] scroll-mt-24">
        <h2 className="font-display text-2xl tracking-tight text-[#FFB000]">$LONO is an in-app token, not money</h2>
        <L>
          <li>$LONO exists only inside LoNo, in LoNo's own records. It is <strong className="text-white">not</strong> a cryptocurrency on a public blockchain.</li>
          <li>It has <strong className="text-white">no cash value</strong>. You can't withdraw, sell or exchange it for money, and LoNo will never buy it back.</li>
          <li>Prices, market cap and charts shown in the app are <strong className="text-white">simulated</strong> for illustration and don't reflect any real market.</li>
          <li>Staking "yield" is a reward rule inside the app, not interest or an investment return. Nothing in LoNo is financial advice.</li>
          <li>We may change reward amounts, caps and staking rules, or reset balances obtained through bugs, abuse or multiple accounts.</li>
          <li>If LoNo closes, $LONO balances end with it.</li>
        </L>
      </section>

      <H id="using">Using LoNo</H>
      <L>
        <li>You need to be old enough to agree to these terms where you live (at least 13, or older where the law requires).</li>
        <li>Keep your password private. You're responsible for activity on your account.</li>
        <li>One account per person. Using several accounts, bots or scripts to earn rewards breaks these terms.</li>
        <li>Don't post anything illegal, hateful, harassing, sexually explicit, misleading, or that you don't have the rights to.</li>
        <li>We may remove content, hide reviews, unpublish courses, or suspend accounts that break these terms. Contact {contact} if you think we got it wrong.</li>
        <li>Rewards are paid for <em>verified</em> watching (time we observe while media plays, with daily limits) and for passing course quizzes.</li>
      </L>

      <H id="creators">Creators</H>
      <L>
        <li>You keep ownership of what you upload. You give LoNo permission to host, stream and show it on the platform while it's published.</li>
        <li>Only upload content you made or have permission to use, including music and footage in your videos.</li>
        <li>Course rewards for learners are set by LoNo, not by creators. Creator payouts are in $LONO and follow the same "no cash value" rules.</li>
        <li>If you use AI tools in LoNo to draft captions, summaries or quiz questions, check them before publishing. You're responsible for what you publish.</li>
      </L>

      <H id="privacy">Your data</H>
      <P>We keep what's needed to run your account: your name, email, password (stored only as a secure hash), wallet history, what you watch and learn, your reviews and votes, and what you upload.</P>
      <L>
        <li><strong className="text-white">See and download it:</strong> <Link to="/settings" className="text-white underline">Settings → Download my data</Link> gives you everything in one file.</li>
        <li><strong className="text-white">Delete it:</strong> <Link to="/settings" className="text-white underline">Settings → Delete account</Link> erases your account and personal data. Totals you contributed to (views, vote counts) stay without any link to you.</li>
        <li><strong className="text-white">Records we keep:</strong> to show we handled requests properly, we keep a short log of consents, data downloads and deletions. After deletion it holds only an internal ID and a one-way fingerprint of your email, not the email itself.</li>
        <li>If AI features are on, the text you send to the assistant, or the lesson text a creator asks it to read, is sent to our AI provider to produce an answer.</li>
        <li>We don't sell your data and LoNo doesn't show third-party ads.</li>
      </L>

      <H id="changes">Changes and contact</H>
      <P>If we change these terms, we'll show the new version and ask you to accept it before you continue. For questions or privacy requests, contact {contact}.</P>
    </div>
  );
}
