import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, ArrowUp, ArrowDown, Trash2, Plus, Loader2, Upload, CheckCircle2, AlertCircle, ExternalLink, X, Sparkles } from "lucide-react";
import { useConfig } from "@/lib/config";
import { api, errorText, resolveMedia } from "@/lib/api";

const field = "w-full bg-white/5 border border-white/10 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FFB000]/40 focus:border-[#FFB000]/40";
const iconBtn = "p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-transparent";
let keySeq = 0;
const k = () => `k${++keySeq}`;

const fromServer = (c) => ({
  title: c.title, description: c.description || "", level: c.level, thumbnail_url: c.thumbnail_url || "",
  pass_mark: c.quiz?.pass_mark ?? 0.75,
  lessons: c.lessons.map((l) => ({ ...l, video_url: l.video_url || "", _k: l.id })),
  questions: c.quiz.questions.map((q) => ({ ...q, explanation: q.explanation || "", _k: q.id })),
});
const toServer = (d) => ({
  ...d,
  lessons: d.lessons.map(({ _k, ...l }) => ({ ...l, video_url: l.video_url || null, duration_sec: Number(l.duration_sec) || 0 })),
  questions: d.questions.map(({ _k, ...q }) => q),
});
const move = (arr, i, dir) => { const a = [...arr]; [a[i], a[i + dir]] = [a[i + dir], a[i]]; return a; };

async function upload(file) {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post("/storage/upload", fd);
  return data.url;
}

function UploadButton({ accept, label, onDone }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <input ref={ref} type="file" accept={accept} className="hidden" onChange={async (e) => {
        const f = e.target.files?.[0]; e.target.value = "";
        if (!f) return;
        setBusy(true);
        try { onDone(await upload(f)); toast.success("Uploaded"); }
        catch (err) { toast.error(errorText(err, "Upload failed")); } finally { setBusy(false); }
      }} />
      <button type="button" onClick={() => ref.current?.click()} disabled={busy}
        className="shrink-0 flex items-center gap-1.5 text-xs bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-3 py-2.5 disabled:opacity-50">
        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />} {label}
      </button>
    </>
  );
}

export default function CourseEditor() {
  const { id } = useParams();
  const nav = useNavigate();
  const [meta, setMeta] = useState(null);      // status, problems, enrolled... from the server
  const [draft, setDraft] = useState(null);    // what the creator is editing
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const cfg = useConfig();

  useEffect(() => {
    api.get(`/creator/courses/${id}`).then(({ data }) => { setMeta(data); setDraft(fromServer(data)); })
      .catch(() => setMeta(false));
  }, [id]);

  useEffect(() => {
    const warn = (e) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const edit = useCallback((fn) => { setDraft((d) => fn(d)); setDirty(true); }, []);
  const setLesson = (i, patch) => edit((d) => ({ ...d, lessons: d.lessons.map((l, j) => (j === i ? { ...l, ...patch } : l)) }));
  const setQ = (i, patch) => edit((d) => ({ ...d, questions: d.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)) }));

  const save = async ({ quiet = false } = {}) => {
    setBusy(true);
    try {
      const { data } = await api.put(`/creator/courses/${id}`, toServer(draft));
      setMeta(data); setDraft(fromServer(data)); setDirty(false);
      if (!quiet) toast.success("Saved");
      return data;
    } catch (e) { toast.error(errorText(e, "Couldn't save")); return null; } finally { setBusy(false); }
  };

  const publish = async () => {
    const saved = dirty ? await save({ quiet: true }) : meta;
    if (!saved) return;
    if (saved.problems?.length) { toast.error("Fix the items in the checklist first"); return; }
    setBusy(true);
    try {
      await api.post(`/creator/courses/${id}/publish`);
      setMeta((m) => ({ ...m, status: "published" }));
      toast.success("Published", { description: "Your course is live on Learn." });
    } catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };

  const suggest = async () => {
    if (dirty && !(await save({ quiet: true }))) return; // the AI reads the saved lessons
    setSuggesting(true);
    try {
      const { data } = await api.post(`/creator/courses/${id}/suggest-questions`, { count: 3 });
      edit((d) => ({ ...d, questions: [...d.questions, ...data.questions.map((q) => ({ ...q, explanation: q.explanation || "", _k: k() }))] }));
      toast.success(`Added ${data.questions.length} draft questions`, { description: "Check each one, then save." });
    } catch (e) { toast.error(errorText(e, "Couldn't draft questions")); } finally { setSuggesting(false); }
  };

  const unpublish = async () => {
    if (!window.confirm("Take this course off Learn? Learners keep their certificates.")) return;
    await api.post(`/creator/courses/${id}/unpublish`);
    setMeta((m) => ({ ...m, status: "draft" }));
    toast("Course moved back to drafts");
  };

  const remove = async () => {
    if (!window.confirm("Delete this course for good?")) return;
    try { await api.delete(`/creator/courses/${id}`); setDirty(false); nav("/studio"); toast("Course deleted"); }
    catch (e) { toast.error(errorText(e)); }
  };

  if (meta === false) return <div className="min-h-[60vh] grid place-items-center text-gray-400">This course isn't in your studio. <Link to="/studio" className="text-white underline ml-1">Back to Studio</Link></div>;
  if (!draft) return <div className="min-h-[70vh] grid place-items-center"><Loader2 className="w-8 h-8 animate-spin text-[#FF3B30]" /></div>;

  const published = meta.status === "published";
  const problems = meta.problems || [];

  return (
    <div data-testid="course-editor" className="max-w-4xl mx-auto px-4 md:px-8 pt-8 pb-48">
      <Link to="/studio" className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white"><ArrowLeft className="w-4 h-4" /> Studio</Link>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight mr-auto">Edit course</h1>
        <span className={`text-xs px-2.5 py-1 rounded-full border ${published ? "text-[#34C759] border-[#34C759]/30 bg-[#34C759]/10" : "text-gray-300 border-white/15 bg-white/5"}`}>
          {published ? "Published" : "Draft"}
        </span>
        {published && <Link to={`/learn/${id}`} className="text-sm text-gray-300 hover:text-white inline-flex items-center gap-1">View on Learn <ExternalLink className="w-3.5 h-3.5" /></Link>}
      </div>

      {/* Checklist */}
      <div data-testid="checklist" className={`mt-6 p-4 rounded-xl border ${problems.length ? "border-[#FFB000]/30 bg-[#FFB000]/[0.06]" : "border-[#34C759]/30 bg-[#34C759]/[0.06]"}`}>
        {problems.length ? (
          <>
            <div className="flex items-center gap-2 text-sm font-medium text-[#FFB000]"><AlertCircle className="w-4 h-4" /> Before you can publish</div>
            <ul className="mt-2 text-sm text-gray-300 space-y-1 list-disc pl-6">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
          </>
        ) : (
          <div className="flex items-center gap-2 text-sm text-[#34C759]"><CheckCircle2 className="w-4 h-4" /> {published ? "Live on Learn. Changes go live when you save." : "Ready to publish."}</div>
        )}
        {dirty && <p className="mt-2 text-xs text-gray-500">Save to update this checklist.</p>}
      </div>

      {/* Details */}
      <section className="mt-10">
        <h2 className="font-display text-xl">Details</h2>
        <div className="mt-4 space-y-4">
          <label className="block"><span className="text-sm text-gray-400">Title</span>
            <input data-testid="course-title" className={`${field} mt-1.5 text-base`} maxLength={120} value={draft.title} onChange={(e) => edit((d) => ({ ...d, title: e.target.value }))} /></label>
          <label className="block"><span className="text-sm text-gray-400">Description</span>
            <textarea data-testid="course-description" rows={3} maxLength={2000} className={`${field} mt-1.5`} placeholder="What will learners be able to do after this course?"
              value={draft.description} onChange={(e) => edit((d) => ({ ...d, description: e.target.value }))} /></label>
          <div className="grid sm:grid-cols-[180px_1fr] gap-4">
            <label className="block"><span className="text-sm text-gray-400">Level</span>
              <select className={`${field} mt-1.5`} value={draft.level} onChange={(e) => edit((d) => ({ ...d, level: e.target.value }))}>
                {["Beginner", "Intermediate", "Advanced"].map((l) => <option key={l}>{l}</option>)}
              </select></label>
            <div><span className="text-sm text-gray-400">Cover image</span>
              <div className="mt-1.5 flex gap-2">
                <input className={field} placeholder="Image URL" value={draft.thumbnail_url} onChange={(e) => edit((d) => ({ ...d, thumbnail_url: e.target.value }))} />
                <UploadButton accept="image/*" label="Upload" onDone={(url) => edit((d) => ({ ...d, thumbnail_url: url }))} />
              </div>
            </div>
          </div>
          {draft.thumbnail_url && <img loading="lazy" decoding="async" src={resolveMedia(draft.thumbnail_url)} alt="" className="w-48 aspect-[4/3] object-cover rounded-lg ring-1 ring-white/10" />}
        </div>
      </section>

      {/* Lessons */}
      <section className="mt-12">
        <h2 className="font-display text-xl">Lessons</h2>
        <p className="text-sm text-gray-400 mt-1">Learners mark each lesson complete, then take the quiz.</p>
        <ol className="mt-4 space-y-4">
          {draft.lessons.map((l, i) => (
            <li key={l._k} data-testid="lesson-editor" className="p-4 rounded-xl bg-[#121212] border border-white/10">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500 tabular-nums w-6">{i + 1}.</span>
                <input aria-label={`Lesson ${i + 1} title`} className={`${field} font-medium`} placeholder="Lesson title" value={l.title} onChange={(e) => setLesson(i, { title: e.target.value })} />
                <button className={iconBtn} aria-label="Move up" disabled={i === 0} onClick={() => edit((d) => ({ ...d, lessons: move(d.lessons, i, -1) }))}><ArrowUp className="w-4 h-4" /></button>
                <button className={iconBtn} aria-label="Move down" disabled={i === draft.lessons.length - 1} onClick={() => edit((d) => ({ ...d, lessons: move(d.lessons, i, 1) }))}><ArrowDown className="w-4 h-4" /></button>
                <button className={iconBtn} aria-label="Delete lesson" onClick={() => edit((d) => ({ ...d, lessons: d.lessons.filter((_, j) => j !== i) }))}><Trash2 className="w-4 h-4" /></button>
              </div>
              <textarea aria-label={`Lesson ${i + 1} text`} rows={5} className={`${field} mt-3`} placeholder="Lesson text. Leave a blank line between paragraphs."
                value={l.body} onChange={(e) => setLesson(i, { body: e.target.value })} />
              <div className="mt-3 grid sm:grid-cols-[1fr_auto_120px] gap-2 items-center">
                <input className={field} placeholder="Video URL (optional)" value={l.video_url} onChange={(e) => setLesson(i, { video_url: e.target.value })} />
                <UploadButton accept="video/*" label="Upload video" onDone={(url) => setLesson(i, { video_url: url })} />
                <label className="flex items-center gap-2 text-xs text-gray-400">
                  <input type="number" min={0} max={360} className={`${field} w-16 px-2`} value={Math.round((l.duration_sec || 0) / 60)}
                    onChange={(e) => setLesson(i, { duration_sec: Math.max(0, Number(e.target.value)) * 60 })} /> min
                </label>
              </div>
            </li>
          ))}
        </ol>
        <button data-testid="add-lesson" onClick={() => edit((d) => ({ ...d, lessons: [...d.lessons, { _k: k(), title: `Lesson ${d.lessons.length + 1}`, body: "", video_url: "", duration_sec: 300 }] }))}
          className="mt-4 flex items-center gap-2 text-sm bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2"><Plus className="w-4 h-4" /> Add lesson</button>
      </section>

      {/* Quiz */}
      <section className="mt-12">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-display text-xl">Final quiz</h2>
            <p className="text-sm text-gray-400 mt-1">At least 3 questions. Select the correct answer for each. Learners never see answers until they pass.</p>
          </div>
          <label className="text-sm text-gray-400 flex items-center gap-2 whitespace-nowrap">Pass mark
            <select className={`${field} w-24`} value={draft.pass_mark} onChange={(e) => edit((d) => ({ ...d, pass_mark: Number(e.target.value) }))}>
              {[0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1].map((v) => <option key={v} value={v}>{Math.round(v * 100)}%</option>)}
            </select>
          </label>
        </div>
        <ol className="mt-4 space-y-4">
          {draft.questions.map((q, i) => (
            <li key={q._k} data-testid="question-editor" className="p-4 rounded-xl bg-[#121212] border border-white/10">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500 tabular-nums w-6">{i + 1}.</span>
                <input aria-label={`Question ${i + 1}`} className={`${field} font-medium`} placeholder="Question" value={q.prompt} onChange={(e) => setQ(i, { prompt: e.target.value })} />
                <button className={iconBtn} aria-label="Delete question" onClick={() => edit((d) => ({ ...d, questions: d.questions.filter((_, j) => j !== i) }))}><Trash2 className="w-4 h-4" /></button>
              </div>
              <fieldset className="mt-3 pl-8 space-y-2">
                <legend className="sr-only">Answers for question {i + 1}</legend>
                {q.options.map((o, oi) => (
                  <div key={oi} className="flex items-center gap-2">
                    <input type="radio" name={`correct-${q._k}`} aria-label={`Answer ${oi + 1} is correct`} className="accent-[#34C759] w-4 h-4"
                      checked={q.answer_index === oi} onChange={() => setQ(i, { answer_index: oi })} />
                    <input aria-label={`Answer ${oi + 1}`} className={`${field} ${q.answer_index === oi ? "border-[#34C759]/50" : ""}`} placeholder={`Answer ${oi + 1}`}
                      value={o} onChange={(e) => setQ(i, { options: q.options.map((x, j) => (j === oi ? e.target.value : x)) })} />
                    <button className={iconBtn} aria-label="Remove answer" disabled={q.options.length <= 2}
                      onClick={() => setQ(i, { options: q.options.filter((_, j) => j !== oi), answer_index: q.answer_index === oi ? 0 : q.answer_index > oi ? q.answer_index - 1 : q.answer_index })}>
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                {q.options.length < 6 && (
                  <button className="text-xs text-gray-400 hover:text-white" onClick={() => setQ(i, { options: [...q.options, ""] })}>+ Add answer</button>
                )}
                <input className={`${field} mt-2`} placeholder="Explanation shown after passing (optional)" value={q.explanation} onChange={(e) => setQ(i, { explanation: e.target.value })} />
              </fieldset>
            </li>
          ))}
        </ol>
        <div className="flex flex-wrap items-center gap-x-4">
        <button data-testid="add-question" onClick={() => edit((d) => ({ ...d, questions: [...d.questions, { _k: k(), prompt: "", options: ["", ""], answer_index: 0, explanation: "" }] }))}
          className="mt-4 flex items-center gap-2 text-sm bg-white/5 hover:bg-white/10 border border-white/10 rounded-full px-4 py-2"><Plus className="w-4 h-4" /> Add question</button>
        {cfg.ai && (
          <button data-testid="suggest-questions" onClick={suggest} disabled={suggesting || busy}
            className="mt-4 flex items-center gap-2 text-sm text-[#FFB000] hover:text-[#FFC740] px-1 py-2 disabled:opacity-50">
            {suggesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {suggesting ? "Drafting questions from your lessons…" : "Draft 3 questions from my lessons with AI"}
          </button>
        )}
        </div>
      </section>

      <section className="mt-16 pt-6 border-t border-white/10 flex flex-wrap gap-3 text-sm">
        {published && <button onClick={unpublish} className="text-gray-300 hover:text-white">Unpublish</button>}
        <button onClick={remove} className="text-[#FF8A82] hover:text-[#FF3B30]">Delete course</button>
      </section>

      {/* Action bar, kept above the mobile tab bar */}
      <div className="fixed inset-x-0 bottom-16 lg:bottom-0 z-40 bg-[#050505]/95 backdrop-blur border-t border-white/10">
        <div className="max-w-4xl mx-auto px-4 md:px-8 py-3 flex items-center gap-3">
          <span className="text-sm text-gray-400 mr-auto">{busy ? "Working…" : dirty ? "Unsaved changes" : "All changes saved"}</span>
          <button data-testid="save-course" onClick={() => save()} disabled={busy || !dirty}
            className="rounded-full px-5 py-2.5 text-sm font-medium bg-white/10 hover:bg-white/15 disabled:opacity-40">Save</button>
          {!published && (
            <button data-testid="publish-course" onClick={publish} disabled={busy}
              className="rounded-full px-5 py-2.5 text-sm font-medium bg-[#FF3B30] hover:bg-[#FF5C53] disabled:opacity-40">Publish</button>
          )}
        </div>
      </div>
    </div>
  );
}
