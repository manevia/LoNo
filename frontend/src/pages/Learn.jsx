import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, resolveMedia } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Loader2, Award, Coins } from "lucide-react";

export default function Learn() {
  const { user } = useAuth();
  const [courses, setCourses] = useState(null);

  useEffect(() => { api.get("/learn/courses").then(({ data }) => setCourses(data)).catch(() => setCourses([])); }, [user]);

  if (!courses) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  const inProgress = courses.filter((c) => c.progress.enrolled && !c.progress.passed);
  const totalReward = courses.reduce((n, c) => n + (c.progress.passed ? 0 : c.reward_lono), 0);

  return (
    <div data-testid="learn-page" className="max-w-[1200px] mx-auto px-4 md:px-8 pt-10 pb-32">
      <h1 className="font-display text-4xl md:text-6xl font-semibold tracking-tighter max-w-3xl leading-[0.95]">
        Learn something.<br />Get paid for it.
      </h1>
      <p className="mt-5 text-gray-400 max-w-xl leading-relaxed">
        Short courses from LoNo creators. Finish the lessons, pass the quiz, and you get a certificate anyone can verify,
        plus $LONO in your wallet{totalReward > 0 ? `: ${totalReward} available across these courses` : ""}.
      </p>

      {inProgress.length > 0 && (
        <section className="mt-12">
          <h2 className="font-display text-xl mb-4">Pick up where you left off</h2>
          <div className="space-y-3">
            {inProgress.map((c) => (
              <Link key={c.id} to={`/learn/${c.id}`} className="flex items-center gap-4 p-4 rounded-xl bg-white/[0.03] border border-white/10 hover:border-white/25 transition">
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{c.title}</div>
                  <div className="mt-2 h-1.5 bg-white/10 rounded-full overflow-hidden max-w-sm">
                    <div className="h-full bg-[#FFB000] rounded-full" style={{ width: `${c.progress.percent}%` }} />
                  </div>
                </div>
                <span className="text-sm text-gray-400 tabular-nums">{c.progress.lessons_done}/{c.progress.lessons_total} lessons</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="mt-14">
        <h2 className="font-display text-xl mb-4">All courses</h2>
        <div className="divide-y divide-white/10 border-y border-white/10">
          {courses.map((c) => (
            <Link key={c.id} to={`/learn/${c.id}`} data-testid={`course-${c.id}`}
              className="group grid grid-cols-[96px_1fr] md:grid-cols-[180px_1fr_auto] gap-5 py-6 items-center">
              <img src={resolveMedia(c.thumbnail_url)} alt="" className="w-full aspect-[4/3] object-cover rounded-lg ring-1 ring-white/10" />
              <div className="min-w-0">
                <div className="text-xs text-gray-400">{c.level} / {c.lessons.length} lessons / {Math.round(c.lessons.reduce((n, l) => n + l.duration_sec, 0) / 60)} min</div>
                <h3 className="mt-1 font-display text-2xl tracking-tight group-hover:text-[#FFB000] transition-colors">{c.title}</h3>
                <p className="mt-1 text-sm text-gray-400 max-w-xl line-clamp-2">{c.description}</p>
              </div>
              <div className="col-span-2 md:col-span-1 flex md:flex-col items-center md:items-end gap-3 md:gap-1 text-sm">
                {c.progress.passed ? (
                  <span className="flex items-center gap-1.5 text-[#34C759]"><Award className="w-4 h-4" /> Certified</span>
                ) : (
                  <span className="flex items-center gap-1.5 text-[#FFB000]"><Coins className="w-4 h-4" /> {c.reward_lono} $LONO</span>
                )}
                <span className="text-gray-500">{c.enrolled || 0} enrolled</span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
