import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errorText } from "@/lib/api";
import { Stars, StarPicker } from "@/components/Stars";

/** Reviews for a course: summary, the viewer's own review form (if they passed), and the list. */
export default function CourseReviews({ courseId, passed, onChange }) {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ rating: 0, text: "" });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const { data } = await api.get(`/learn/courses/${courseId}/reviews`);
    setData(data);
    if (data.mine) setForm({ rating: data.mine.rating, text: data.mine.text || "" });
  }, [courseId]);

  useEffect(() => { load().catch(() => setData(false)); }, [load, passed]);

  if (!data) return null;
  const { summary, items, mine, can_review } = data;

  const save = async (e) => {
    e.preventDefault();
    if (!form.rating) { toast.error("Pick a star rating first"); return; }
    setBusy(true);
    try {
      await api.put(`/learn/courses/${courseId}/review`, form);
      toast.success(mine ? "Review updated" : "Thanks for your review");
      setEditing(false); await load(); onChange?.();
    } catch (err) { toast.error(errorText(err, "Your review wasn't saved")); } finally { setBusy(false); }
  };

  const remove = async () => {
    if (!window.confirm("Delete your review?")) return;
    try {
      await api.delete(`/learn/courses/${courseId}/review`);
      setForm({ rating: 0, text: "" }); setEditing(false); await load(); onChange?.();
    } catch (err) { toast.error(errorText(err)); }
  };

  const showForm = can_review && (!mine || editing);
  const max = Math.max(1, ...Object.values(summary.distribution));

  return (
    <section data-testid="course-reviews" className="mt-20 pt-10 border-t border-white/10" aria-labelledby="reviews-heading">
      <h2 id="reviews-heading" className="font-display text-2xl">Reviews</h2>
      <p className="mt-1 text-sm text-gray-400">Only learners who passed the course can leave a review.</p>

      <div className="mt-8 grid md:grid-cols-[260px_1fr] gap-10">
        <div>
          {summary.count ? (
            <>
              <div className="flex items-baseline gap-3">
                <span className="font-display text-5xl tabular-nums">{summary.average.toFixed(1)}</span>
                <Stars value={summary.average} />
              </div>
              <div className="mt-1 text-sm text-gray-400">{summary.count} review{summary.count === 1 ? "" : "s"}</div>
              <dl className="mt-5 space-y-1.5">
                {[5, 4, 3, 2, 1].map((n) => (
                  <div key={n} className="grid grid-cols-[1.5rem_1fr_1.5rem] items-center gap-2 text-xs text-gray-400">
                    <dt className="tabular-nums">{n}★</dt>
                    <dd className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                      <div className="h-full bg-[#FFB000] rounded-full" style={{ width: `${(summary.distribution[n] / max) * 100}%` }} />
                    </dd>
                    <dd className="tabular-nums text-right">{summary.distribution[n]}</dd>
                  </div>
                ))}
              </dl>
            </>
          ) : (
            <p className="text-gray-400">No reviews yet.{can_review ? " Be the first." : ""}</p>
          )}
        </div>

        <div className="min-w-0">
          {showForm && (
            <form onSubmit={save} data-testid="review-form" className="p-5 rounded-xl bg-[#121212] border border-white/10 mb-8">
              <div className="font-medium mb-3">{mine ? "Edit your review" : "How was this course?"}</div>
              <StarPicker value={form.rating} onChange={(rating) => setForm((f) => ({ ...f, rating }))} />
              <textarea aria-label="Review text" rows={3} maxLength={1000} value={form.text} onChange={(e) => setForm((f) => ({ ...f, text: e.target.value }))}
                placeholder="What did you learn? Who would you recommend it to? (optional)"
                className="mt-4 w-full bg-white/5 border border-white/10 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FFB000]/40" />
              <div className="mt-3 flex items-center gap-3">
                <button data-testid="review-submit" disabled={busy} className="bg-[#FF3B30] hover:bg-[#FF5C53] rounded-full px-5 py-2 text-sm font-medium disabled:opacity-50">
                  {mine ? "Save changes" : "Post review"}
                </button>
                {mine && <button type="button" onClick={() => { setEditing(false); setForm({ rating: mine.rating, text: mine.text || "" }); }} className="text-sm text-gray-400 hover:text-white">Cancel</button>}
                <span className="ml-auto text-xs text-gray-500 tabular-nums">{form.text.length}/1000</span>
              </div>
            </form>
          )}

          {items.length > 0 && (
            <ul className="divide-y divide-white/10">
              {items.map((r) => {
                const isMine = mine && r.id === mine.id;
                return (
                  <li key={r.id} className="py-5 first:pt-0">
                    <div className="flex items-center gap-3">
                      <img loading="lazy" decoding="async" src={r.avatar_url} alt="" className="w-9 h-9 rounded-full bg-white/10" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{r.user_name}{isMine && <span className="text-gray-500 font-normal"> (you)</span>}</div>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                          <Stars value={r.rating} size="w-3.5 h-3.5" />
                          <span>{new Date(r.updated_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                      {isMine && !editing && (
                        <div className="ml-auto flex gap-3 text-xs">
                          <button onClick={() => setEditing(true)} className="text-gray-300 hover:text-white">Edit</button>
                          <button onClick={remove} className="text-[#FF8A82] hover:text-[#FF3B30]">Delete</button>
                        </div>
                      )}
                    </div>
                    {r.text && <p className="mt-3 text-sm text-gray-300 leading-relaxed whitespace-pre-line max-w-[68ch]">{r.text}</p>}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
