import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText, resolveMedia } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Loader2, CheckCircle2, Circle, Lock, Award, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import CourseReviews from "@/components/CourseReviews";
import { Stars } from "@/components/Stars";

export default function Course() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user, refresh } = useAuth();
  const [course, setCourse] = useState(null);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);

  const load = async () => {
    const { data } = await api.get(`/learn/courses/${id}`);
    setCourse(data);
    setActive((a) => a || data.lessons.find((l) => !data.progress.completed_lessons.includes(l.id))?.id || data.lessons[0]?.id);
  };
  useEffect(() => {
    load().catch(() => setCourse(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, user]);

  const p = course?.progress;
  const lesson = useMemo(() => course?.lessons?.find((l) => l.id === active), [course, active]);
  const allDone = p && p.lessons_done === p.lessons_total;

  if (course === false) return <div className="min-h-[60vh] grid place-items-center text-gray-400">This course doesn't exist. <Link to="/learn" className="text-[#FF3B30] ml-1">See all courses</Link></div>;
  if (!course) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  const enroll = async () => {
    if (!user) { nav("/signup"); return; }
    setBusy(true);
    try { await api.post(`/learn/courses/${id}/enroll`); await load(); toast.success("You're enrolled"); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };

  const complete = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/learn/courses/${id}/lessons/${lesson.id}/complete`);
      setCourse((c) => ({ ...c, progress: { ...c.progress, ...data } }));
      const next = course.lessons.find((l) => !data.completed_lessons.includes(l.id));
      if (next) setActive(next.id); else setActive("quiz");
    } catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };

  const submit = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/learn/courses/${id}/quiz`, { answers });
      setResult(data);
      if (data.reward > 0) { toast.success(`Passed! +${data.reward} $LONO`, { description: "Your certificate is ready" }); refresh(); }
      else if (!data.passed) toast(`You scored ${Math.round(data.score * 100)}%. You need ${Math.round(data.pass_mark * 100)}% to pass.`);
      await load();
    } catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };

  const qCount = course.quiz.questions.length;
  const answered = Object.keys(answers).length;
  const byQ = Object.fromEntries((result?.results || []).map((r) => [r.id, r]));

  return (
    <div data-testid="course-page" className="max-w-[1400px] mx-auto px-4 md:px-8 pt-8 pb-32">
      <Link to="/learn" className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white"><ArrowLeft className="w-4 h-4" /> All courses</Link>
      <div className="mt-4 flex flex-wrap items-end gap-6 justify-between">
        <div className="max-w-2xl">
          <div className="text-sm text-gray-400 flex flex-wrap items-center gap-x-2">
            <span>{course.level} / {course.reward_lono} $LONO for passing</span>
            {course.rating_count > 0 && (
              <a href="#reviews-heading" className="inline-flex items-center gap-1.5 hover:text-white">
                / <Stars value={course.rating_avg} size="w-3.5 h-3.5" /> {course.rating_avg.toFixed(1)} ({course.rating_count})
              </a>
            )}
          </div>
          <h1 className="mt-1 font-display text-3xl md:text-5xl font-semibold tracking-tighter">{course.title}</h1>
          <p className="mt-3 text-gray-400">{course.description}</p>
        </div>
        {!p.enrolled ? (
          <button data-testid="enroll-btn" onClick={enroll} disabled={busy} className="bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full px-6 py-3 font-medium disabled:opacity-50">
            {user ? "Start course" : "Sign up to start"}
          </button>
        ) : p.passed ? (
          <Link to={`/certificates/${p.certificate_id}`} className="flex items-center gap-2 rounded-full px-5 py-3 bg-[#34C759]/15 text-[#34C759] border border-[#34C759]/30">
            <Award className="w-4 h-4" /> View your certificate
          </Link>
        ) : (
          <div className="text-sm text-gray-400 tabular-nums">{p.lessons_done} of {p.lessons_total} lessons done</div>
        )}
      </div>

      <div className="mt-10 grid lg:grid-cols-[320px_1fr] gap-8">
        <nav aria-label="Lessons" className="lg:sticky lg:top-24 self-start">
          <ol className="space-y-1">
            {course.lessons.map((l, i) => {
              const done = p.completed_lessons.includes(l.id);
              return (
                <li key={l.id}>
                  <button onClick={() => setActive(l.id)} aria-current={active === l.id}
                    className={`w-full text-left flex items-start gap-3 px-3 py-3 rounded-lg transition ${active === l.id ? "bg-white/10" : "hover:bg-white/5"}`}>
                    {done ? <CheckCircle2 className="w-5 h-5 text-[#34C759] shrink-0 mt-0.5" /> : <Circle className="w-5 h-5 text-gray-600 shrink-0 mt-0.5" />}
                    <span className="flex-1"><span className="text-gray-500 tabular-nums mr-2">{i + 1}.</span>{l.title}</span>
                    <span className="text-xs text-gray-500 mt-0.5">{Math.round(l.duration_sec / 60)}m</span>
                  </button>
                </li>
              );
            })}
            <li>
              <button onClick={() => setActive("quiz")} disabled={!allDone}
                className={`w-full text-left flex items-start gap-3 px-3 py-3 rounded-lg transition disabled:opacity-50 ${active === "quiz" ? "bg-white/10" : "hover:bg-white/5"}`}>
                {p.passed ? <Award className="w-5 h-5 text-[#FFB000] shrink-0 mt-0.5" /> : allDone ? <Circle className="w-5 h-5 text-[#FFB000] shrink-0 mt-0.5" /> : <Lock className="w-5 h-5 text-gray-600 shrink-0 mt-0.5" />}
                <span className="flex-1">Final quiz{!allDone && <span className="block text-xs text-gray-500">Unlocks after the last lesson</span>}</span>
              </button>
            </li>
          </ol>
        </nav>

        <section className="min-w-0">
          {active === "quiz" ? (
            <div data-testid="quiz" className="max-w-2xl">
              <h2 className="font-display text-2xl">Final quiz</h2>
              <p className="mt-1 text-sm text-gray-400">{qCount} questions. Score {Math.round(course.quiz.pass_mark * 100)}% or more to pass. You can retake it.</p>
              <ol className="mt-8 space-y-8">
                {course.quiz.questions.map((q, qi) => (
                  <li key={q.id}>
                    <fieldset>
                      <legend className="font-medium"><span className="text-gray-500 mr-2 tabular-nums">{qi + 1}.</span>{q.prompt}</legend>
                      <div className="mt-3 space-y-2">
                        {q.options.map((o, oi) => {
                          const r = byQ[q.id];
                          const picked = answers[q.id] === oi;
                          const revealed = r && r.answer_index !== undefined;
                          const tone = revealed ? (oi === r.answer_index ? "border-[#34C759]/60 bg-[#34C759]/10" : "border-white/10")
                            : r && picked ? (r.correct ? "border-[#34C759]/60 bg-[#34C759]/10" : "border-[#FF3B30]/60 bg-[#FF3B30]/10")
                            : picked ? "border-[#FFB000]/70 bg-[#FFB000]/10" : "border-white/10 hover:border-white/25";
                          return (
                            <label key={oi} className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition ${tone}`}>
                              <input type="radio" name={q.id} className="accent-[#FFB000]" checked={picked} disabled={!!result?.passed}
                                onChange={() => {
                                  setAnswers((a) => ({ ...a, [q.id]: oi }));
                                  setResult((res) => res && { ...res, results: res.results.filter((x) => x.id !== q.id) });
                                }} />
                              <span className="text-sm">{o}</span>
                            </label>
                          );
                        })}
                      </div>
                      {byQ[q.id] && (
                        <p className={`mt-2 text-sm ${byQ[q.id].correct ? "text-[#34C759]" : "text-[#FF8A82]"}`}>
                          {byQ[q.id].correct ? "Correct." : "Not quite. Review the lessons and try another answer."} {byQ[q.id].explanation || ""}
                        </p>
                      )}
                    </fieldset>
                  </li>
                ))}
              </ol>
              {result?.passed || p.passed ? (
                <Link to={`/certificates/${result?.certificate_id || p.certificate_id}`} className="mt-10 inline-flex items-center gap-2 bg-[#34C759] text-black rounded-full px-6 py-3 font-medium">
                  <Award className="w-4 h-4" /> See your certificate
                </Link>
              ) : (
                <button data-testid="quiz-submit" onClick={submit} disabled={busy || answered < qCount}
                  className="mt-10 bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full px-6 py-3 font-medium disabled:opacity-50">
                  {answered < qCount ? `Answer all ${qCount} questions` : result ? "Try again" : "Submit answers"}
                </button>
              )}
            </div>
          ) : lesson && (
            <article data-testid="lesson">
              {p.enrolled ? (
                <video key={lesson.id} src={resolveMedia(lesson.video_url)} poster={resolveMedia(course.thumbnail_url)} controls playsInline
                  className="w-full aspect-video rounded-2xl bg-black ring-1 ring-white/10" />
              ) : (
                <div className="relative aspect-video rounded-2xl overflow-hidden ring-1 ring-white/10">
                  <img src={resolveMedia(course.thumbnail_url)} alt="" className="absolute inset-0 w-full h-full object-cover opacity-40" />
                  <div className="absolute inset-0 grid place-items-center text-center p-6">
                    <div><Lock className="w-6 h-6 mx-auto text-gray-300" /><p className="mt-2 text-gray-300">Start the course to watch lessons</p></div>
                  </div>
                </div>
              )}
              <h2 className="mt-8 font-display text-2xl md:text-3xl tracking-tight">{lesson.title}</h2>
              <div className="mt-4 max-w-[68ch] space-y-4 text-gray-300 leading-relaxed">
                {lesson.body.split(/\n\s*\n/).map((para, i) => <p key={i}>{para}</p>)}
              </div>
              {p.enrolled && (
                p.completed_lessons.includes(lesson.id) ? (
                  <p className="mt-8 flex items-center gap-2 text-[#34C759]"><CheckCircle2 className="w-4 h-4" /> Lesson complete</p>
                ) : (
                  <button data-testid="complete-lesson" onClick={complete} disabled={busy} className="mt-8 bg-white text-black rounded-full px-6 py-3 font-medium hover:bg-gray-200 disabled:opacity-50">
                    Mark lesson complete
                  </button>
                )
              )}
            </article>
          )}
        </section>
      </div>

      <CourseReviews courseId={id} passed={p.passed} onChange={load} />
    </div>
  );
}
