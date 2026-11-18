import io, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["JWT_SECRET"] = "test-secret"
import database as db, security, study_ai as ai
from pptx import Presentation
from pptx.util import Inches

SAMPLE = r"""=== CARD | p=9
Q: What is $E=mc^2$?
A: Mass-energy equivalence, where $c$ is the speed of light.
=== CARD | p=2
**Q:** Define a \frac{a}{b} fraction.
**A:** A ratio of $a$ to $b$.
=== QUIZ | p=5
Q: Which is $\theta$?
A) an angle
B) a length
C) a mass
D) a time
ANSWER: A
WHY: Theta is an angle.
=== QUIZ | p=6
Q: Broken question
A) one
B) one
ANSWER: A
=== MAP
```mermaid
flowchart TD
A["Energy"] -->|relates| B["Mass"]
style A fill:#f00
click A "http://x"
```
"""

def test_parse():
    p = ai.parse_response(SAMPLE)
    assert [c["source"] for c in p["flashcards"]] == [2, 9]          # sorted by page
    assert "\\frac{a}{b}" in p["flashcards"][0]["question"]           # backslashes survive
    assert len(p["quiz"]) == 1 and p["quiz"][0]["answer"] == "an angle"
    assert sorted(p["quiz"][0]["choices"]) == ["a length", "a mass", "a time", "an angle"]
    assert "style" not in p["diagram"] and "click" not in p["diagram"] and p["diagram"].startswith("flowchart TD")

def test_finish_and_even_selection():
    pack = ai.finish_pack(SAMPLE, 5, 3, [])
    assert any("flashcards" in w for w in pack["warnings"])
    assert ai.select_evenly(list(range(10)), 4) == [0, 3, 6, 9]

def test_quotas_cover_everything():
    lec = ai.Lecture("pdf", ["word " * 50] * 47)
    plan = ai.plan_sections(lec, 30, 12)
    assert plan[0][0][0] == 1 and plan[-1][0][1] == 47
    assert sum(c for _, c, _ in plan) == 30 and sum(q for _, _, q in plan) == 12
    assert all(c >= 1 for _, c, _ in plan)
    cards, quiz = ai.suggest_counts(lec)
    assert 6 <= cards <= 50 and 5 <= quiz <= 30

def test_pptx_reading():
    prs = Presentation(); s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Derivatives"
    t = s.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1)).table
    t.cell(0, 0).text, t.cell(0, 1).text = "x", "f(x)"
    s.notes_slide.notes_text_frame.text = "explain slope"
    buf = io.BytesIO(); prs.save(buf)
    lec = ai.read_pptx(buf.getvalue(), True)
    assert "Derivatives" in lec.units[0] and "x | f(x)" in lec.units[0] and "explain slope" in lec.units[0]

def test_db_and_security():
    h = security.hash_password("hunter2hunter2")
    assert security.verify_password("hunter2hunter2", h) and not security.verify_password("nope", h)
    uid = db.create_user("a@b.co", h) if (db.init_db() or True) else None
    assert uid and db.create_user("a@b.co", h) is None
    other = db.create_user("c@d.co", h)
    assert security.read_token(security.make_token(uid)) == uid and security.read_token("junk") is None
    saved = db.save_set(uid, {"filename": "x.pdf", "flashcards": [], "quiz": [], "diagram": "flowchart TD\nA"})
    assert db.save_set(uid, {**saved, "filename": "y.pdf"})["id"] == saved["id"]        # update, not duplicate
    assert len(db.list_sets(uid)) == 1 and db.list_sets(other) == []
    assert db.save_set(other, {**saved})["id"] != saved["id"]                             # cannot overwrite others'
    assert not db.delete_set(other, saved["id"]) and db.delete_set(uid, saved["id"])
    db.cache_put("k", {"a": 1}); assert db.cache_get("k") == {"a": 1} and db.cache_get("z") is None
    rl = security.RateLimiter(2, 60); assert rl.hit("u") and rl.hit("u") and not rl.hit("u")

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)

def test_daily_limit_refund_and_dedupe():
    db.init_db(); uid = db.create_user("limit@x.co", "h")
    ids = [db.reserve_generation(uid, 2), db.reserve_generation(uid, 2)]
    assert all(ids) and db.reserve_generation(uid, 2) is None
    db.refund_generation(ids[0]); assert db.reserve_generation(uid, 2)
    dup = "=== CARD | p=1\nQ: Same?\nA: yes\n=== CARD | p=2\nQ: same?\nA: yes again\n"
    assert len(ai.parse_response(dup)["flashcards"]) == 1
    security.burn_time("x")

if __name__ == "__main__":
    test_daily_limit_refund_and_dedupe(); print("ok test_daily_limit_refund_and_dedupe")
