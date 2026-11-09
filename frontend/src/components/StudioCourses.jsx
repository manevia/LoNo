import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GraduationCap, Plus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, errorText, resolveMedia } from "@/lib/api";

const STATUS = {
  published: "text-[#34C759] bg-[#34C759]/10 border-[#34C759]/30",
  draft: "text-gray-300 bg-white/5 border-white/15",
};

/** Studio section: the creator's courses, with a button to start a new one. */
export default function StudioCourses() {
  const nav = useNavigate();
  const [items, setItems] = useState(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => { api.get("/creator/courses").then(({ data }) => setItems(data)).catch(() => setItems([])); }, []);

  const create = async () => {
    setCreating(true);
    try {
      const { data } = await api.post("/creator/courses", { title: "Untitled course" });
      nav(`/studio/courses/${data.id}`);
    } catch (e) { toast.error(errorText(e)); setCreating(false); }
  };

  return (
    <section className="mt-10" data-testid="studio-courses">
      <div className="flex items-end justify-between gap-4 mb-4">
        <div>
          <h2 className="font-display text-2xl">Courses</h2>
          <p className="text-sm text-gray-400 mt-1">Teach what you know. You earn $LONO each time a learner passes your course.</p>
        </div>
        <button data-testid="new-course" onClick={create} disabled={creating}
          className="shrink-0 flex items-center gap-2 bg-white text-black rounded-full px-5 py-2.5 text-sm font-medium hover:bg-gray-200 disabled:opacity-60">
          {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} New course
        </button>
      </div>
      {items === null ? (
        <Loader2 className="w-6 h-6 animate-spin text-gray-500" />
      ) : items.length === 0 ? (
        <div className="p-8 rounded-2xl border border-dashed border-white/10 text-center text-gray-400">
          <GraduationCap className="w-8 h-8 mx-auto mb-2 opacity-50" />
          No courses yet. A course is a few short lessons and a quiz; learners who pass get a certificate.
        </div>
      ) : (
        <ul className="divide-y divide-white/10 border-y border-white/10">
          {items.map((c) => (
            <li key={c.id}>
              <Link to={`/studio/courses/${c.id}`} className="grid grid-cols-[72px_1fr_auto] gap-4 items-center py-4 hover:bg-white/[0.02]">
                <img src={resolveMedia(c.thumbnail_url)} alt="" className="w-full aspect-[4/3] object-cover rounded-md ring-1 ring-white/10" />
                <div className="min-w-0">
                  <div className="font-medium truncate">{c.title}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    {c.lessons} lessons / {c.questions} questions
                    {c.status === "published" && ` / ${c.enrolled} enrolled / ${c.certificates_issued} passed`}
                    {c.rating_count > 0 && ` / ★ ${c.rating_avg.toFixed(1)} (${c.rating_count})`}
                    {c.status === "draft" && !c.ready && " / not ready to publish yet"}
                  </div>
                </div>
                <span className={`text-xs px-2.5 py-1 rounded-full border capitalize ${STATUS[c.status] || STATUS.draft}`}>{c.status}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
