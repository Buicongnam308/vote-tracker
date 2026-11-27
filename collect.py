#!/usr/bin/env python3
"""Thu thap vote 1 lan (GitHub Actions chay file nay moi 5 phut).

- Mo trang bang trinh duyet an, bat API ma trang goi, lay (ten, so vote).
- Them 1 dong vao data/history.jsonl (lich su de tinh tang truong).
- Dung docs/data.json cho trang web doc.

Chay thu:  python collect.py --debug   (in ra moi API JSON ma trang goi)
"""
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = json.loads(Path(os.environ.get("VOTE_CONFIG", BASE / "config.json")).read_text(encoding="utf-8"))
HISTORY = Path(os.environ.get("VOTE_HISTORY", BASE / "data" / "history.jsonl"))
OUT = Path(os.environ.get("VOTE_OUT", BASE / "docs" / "data.json"))
TARGET = CONFIG["target"]
MAX_POINTS = 4000  # so luot do toi da dua len trang (5 phut/lan ~ 14 ngay)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


# ---------------------------------------------------------------- helpers
def norm(s):
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", s).strip().lower()


def is_target(name):
    return norm(TARGET) in norm(name)


def parse_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str) and re.fullmatch(r"\d{1,3}([.,]\d{3})+|\d+", v.strip()):
        return int(re.sub(r"[.,]", "", v.strip()))
    return None


def active(board):
    return board["url"].startswith("http")


# ---------------------------------------------------------------- tach du lieu
NAME_KEY = re.compile(r"name|title|ten|label", re.I)
BAD_NAME_KEY = re.compile(r"url|image|img|slug|desc|avatar|photo|link|category", re.I)
VOTE_KEY = re.compile(r"vote|score|point|diem|count|total", re.I)
BAD_VOTE_KEY = re.compile(r"(^|\.)id$|rank|order|index|page|limit|size|percent|rate$", re.I)


def flat(d, prefix="", depth=0):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and depth < 2:
            out.update(flat(v, key + ".", depth + 1))
        else:
            out[key] = v
    return out


def find_candidates(obj):
    """Tim mang doi tuong co (ten, so vote) trong JSON bat ky -> [(ten, vote)]."""
    best = []

    def walk(o):
        nonlocal best
        if isinstance(o, list) and len(o) >= 2 and all(isinstance(x, dict) for x in o):
            rows = []
            for x in o:
                f = flat(x)
                name = next((v for k, v in f.items()
                             if isinstance(v, str) and NAME_KEY.search(k) and not BAD_NAME_KEY.search(k)
                             and parse_int(v) is None and v.strip()), None)
                votes = None
                for k, v in f.items():
                    n = parse_int(v)
                    if n is not None and VOTE_KEY.search(k) and not BAD_VOTE_KEY.search(k):
                        votes = n if votes is None else max(votes, n)
                if name and votes is not None:
                    rows.append((name.strip(), votes))
            if len(rows) >= 2 and len(rows) > len(best):
                best = rows
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return best


def parse_text(text):
    """Du phong: doc van ban trang. Dang: ten / hang / so vote."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    rows = {}
    for i, l in enumerate(lines):
        if not re.fullmatch(r"\d{1,3}(\.\d{3})+|\d{2,}", l):
            continue
        votes = parse_int(l)
        if votes is None or votes < 10:
            continue
        for j in range(i - 1, max(i - 4, -1), -1):
            c = lines[j]
            if re.search(r"[^\W\d_]", c):
                rows[c] = max(votes, rows.get(c, 0))
                break
    return list(rows.items())


# ---------------------------------------------------------------- thu thap

SECTION_JS = r"""
(want) => {
  const norm = t => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\u0111/g, "d").replace(/\u0110/g, "D")
                     .replace(/\s+/g, " ").trim().toLowerCase();
  const w = norm(want);
  const secs = [...document.querySelectorAll("[data-category-id]")];
  const sec = secs.find(s => { const h = s.querySelector("h1,h2,h3"); return h && norm(h.textContent) === w; })
           || secs.find(s => { const h = s.querySelector("h1,h2,h3"); return h && norm(h.textContent).includes(w); });
  if (!sec) return { found: false, titles: secs.map(s => (s.querySelector("h1,h2,h3") || {}).textContent) };
  sec.scrollIntoView({ block: "start" });
  const rows = {};
  sec.querySelectorAll("article").forEach(a => {
    const link = a.querySelector("a[href*='/candidate/']");
    if (!link) return;
    const lines = a.innerText.split("\n").map(x => x.trim()).filter(Boolean);
    const name = (link.getAttribute("aria-label") || (a.querySelector("img[alt]:not([alt=''])") || {}).alt || "").trim();
    const i = lines.findIndex(x => x === name);
    const num = lines.slice(i < 0 ? 0 : i + 1).find(x => /^\d{1,3}(\.\d{3})*$/.test(x));
    if (name && num) rows[link.getAttribute("href")] = [name, num];
  });
  return { found: true, rows: Object.values(rows) };
}
"""


def read_section(page, title):
    """Doc (ten, vote) cua dung hang muc `title`. Trang Male Icon hien MOI hang muc trong 1 trang dai,
    nen phai khoanh dung khoi, neu khong ten Nam o hang muc khac se bi lan vao."""
    last = None
    for _ in range(6):
        res = page.evaluate(SECTION_JS, title)
        last = res
        if res["found"] and len(res["rows"]) >= 2:
            return [(n, parse_int(v)) for n, v in res["rows"] if parse_int(v) is not None]
        page.mouse.wheel(0, 2500)          # keo xuong de trang ve not cac khoi tai cham
        page.wait_for_timeout(1200)
    if last and not last["found"]:
        print(f"  [chan doan] khong thay hang muc '{title}'. Cac hang muc co tren trang: {last['titles']}")
    return []


def click_text(page, text, required):
    """Bam vao phan tu DANG HIEN THI co chu `text` (uu tien khop nguyen cum, roi khop mot phan)."""
    for exact in (True, False):
        loc = page.get_by_text(text, exact=exact)
        try:
            page.wait_for_timeout(300)
            for i in range(min(loc.count(), 12)):
                el = loc.nth(i)
                if el.is_visible():
                    el.click(timeout=8000)
                    return True
        except Exception:  # noqa: BLE001
            pass
    if required:
        raise RuntimeError(f"Khong bam duoc '{text}' tren trang")
    return False


def fetch_board(ctx, board, debug=False):
    page = ctx.new_page()
    hits = []

    def on_response(r):
        try:
            if r.request.resource_type not in ("fetch", "xhr"):
                return
            if "json" not in r.headers.get("content-type", ""):
                return
            rows = find_candidates(r.json())
            if debug:
                print(f"  [json] {r.status} {r.url} -> {len(rows)} thi sinh")
            if rows:
                hits.append((r.url, rows))
        except Exception:
            pass

    page.on("response", on_response)
    try:
        page.goto(board["url"], wait_until="networkidle", timeout=60000)
        if board.get("section"):
            page.wait_for_selector("[data-category-id]", timeout=30000)
            page.wait_for_timeout(1500)
            return read_section(page, board["section"])
        steps = board.get("click") or []
        if isinstance(steps, str):
            steps = [steps] if steps else []
        for k, text in enumerate(steps):
            hits.clear()
            # buoc cuoi (hang muc) bat buoc; cac buoc truoc (VD "Binh chon") bo qua neu da o san trang do
            ok = click_text(page, text, required=(k == len(steps) - 1))
            print(f"  click '{text}': {'ok' if ok else 'khong thay, bo qua'}")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(1500)
        page.wait_for_timeout(2500)
        good = [h for h in hits if any(is_target(n) for n, _ in h[1])]
        if good:
            if debug:
                print(f"  => API chon: {good[-1][0]}")
            return good[-1][1]
        if debug:
            print("  => khong thay API chua ten muc tieu, doc van ban trang")
        text = page.inner_text("body")
        rows = parse_text(text)
        if not any(is_target(n) for n, _ in rows):
            flat_text = " | ".join(l.strip() for l in text.splitlines() if l.strip())
            print(f"  [chan doan] url={page.url} so_thi_sinh_doc_duoc={len(rows)}")
            print(f"  [chan doan] van ban trang: {flat_text[:1200]}")
        return rows
    finally:
        page.close()


# ---------------------------------------------------------------- lich su
def load_history(board_id):
    snaps = []
    if HISTORY.exists():
        for line in HISTORY.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("board") == board_id:
                snaps.append((d["ts"], {n: v for n, v in d["rows"]}))
    snaps.sort(key=lambda s: s[0])
    return snaps


def append_history(board_id, rows):
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": int(time.time()), "board": board_id,
                            "rows": [[n, v] for n, v in rows]}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- tinh toan
def rate(series, hours):
    """Toc do tang (vote/gio) trong cua so `hours` gan nhat; None neu chua du du lieu."""
    t1, v1 = series[-1]
    cutoff = t1 - hours * 3600
    base = None
    for t, v in series:
        if t <= cutoff:
            base = (t, v)
        else:
            break
    if base is None:
        base = series[0]
    dt = t1 - base[0]
    if dt < 120:
        return None
    return (v1 - base[1]) / (dt / 3600)


def compute(board, snaps, now, error=None):
    out = {"id": board["id"], "title": board["title"], "error": error,
           "active": active(board), "empty": not snaps}
    if not snaps:
        return out
    series = {}
    for ts, d in snaps:
        for n, v in d.items():
            series.setdefault(n, []).append((ts, v))
    latest = snaps[-1][0]
    cur = {n: s[-1][1] for n, s in series.items() if s[-1][0] == latest}
    ranked = sorted(cur.items(), key=lambda x: -x[1])
    tname = next((n for n, _ in ranked if is_target(n)), None)
    if tname is None:
        out["empty"] = True
        return out
    tv = cur[tname]
    deadline = hours_left = None
    if board.get("deadline"):
        deadline = datetime.fromisoformat(board["deadline"]).timestamp()
        hours_left = max(0.0, (deadline - now) / 3600)

    r1 = lambda n: rate(series[n], 1)
    r6 = lambda n: rate(series[n], 6)
    r24 = lambda n: rate(series[n], 24)
    t6 = r6(tname)

    table = []
    for i, (n, v) in enumerate(ranked, 1):
        row = {"rank": i, "name": n, "votes": v, "me": n == tname, "r1": r1(n), "r24": r24(n)}
        if v > tv:
            gap = v - tv + 1
            c6 = r6(n)
            row["gap"] = gap
            if hours_left:
                row["need_rate"] = (gap + (c6 or 0) * hours_left) / hours_left
            if t6 is not None and c6 is not None and t6 > c6:
                h = gap / (t6 - c6)
                row["eta_hours"] = h
                row["eta_ts"] = now + h * 3600
                row["eta_in_time"] = deadline is None or now + h * 3600 <= deadline
        elif v < tv:
            row["lead"] = tv - v
        table.append(row)

    # Cac cot hien thi: Nam + nguoi sat ngay tren Nam + them cho du 4 nguoi (gan Nam nhat)
    others = sorted((n for n in cur if n != tname), key=lambda n: abs(cur[n] - tv))
    above = [n for n in others if cur[n] > tv]
    first = min(above, key=lambda n: cur[n]) if above else None
    near = ([first] if first else []) + [n for n in others if n != first]
    names = [tname] + near[:3]

    # Chuoi thoi gian day du (moi luot do 1 diem): ts + v[ten][luot] (None neu luot do thieu ten)
    snaps_tl = snaps[-MAX_POINTS:]
    tl = {"names": names, "ts": [ts for ts, _ in snaps_tl],
          "v": [[d.get(n) for _, d in snaps_tl] for n in names]}
    # Bang bien dong tung luot do: TAT CA thi sinh dang co trong bang xep hang (theo hang hien tai)
    all_names = [n for n, _ in ranked]
    tl["all"] = {"names": all_names, "v": [[d.get(n) for _, d in snaps_tl] for n in all_names]}

    out.update(updated=latest, my_name=tname, my_rank=[r["rank"] for r in table if r["me"]][0],
               my_votes=tv, my_r1=r1(tname), my_r6=t6, my_r24=r24(tname),
               deadline=deadline, hours_left=hours_left, table=table, tl=tl,
               snapshots=len(snaps))
    return out


def write_site(errors):
    now = time.time()
    payload = {"now": now, "target": TARGET,
               "boards": [compute(b, load_history(b["id"]), now, errors.get(b["id"]))
                          for b in CONFIG["boards"]]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- main
def main():
    debug = "--debug" in sys.argv
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.touch(exist_ok=True)
    errors = {}
    boards = [b for b in CONFIG["boards"] if active(b)]
    if boards:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(locale="vi-VN", user_agent=UA)
            for b in boards:
                print(f"[{b['id']}] {b['url']}")
                rows, err = [], None
                for attempt in (1, 2):
                    try:
                        rows = fetch_board(ctx, b, debug)
                        if rows and any(is_target(n) for n, _ in rows):
                            break
                        err = f"Khong thay '{TARGET}' trong du lieu lay duoc"
                    except Exception as e:  # noqa: BLE001
                        err = str(e)[:200]
                    time.sleep(3)
                if rows and any(is_target(n) for n, _ in rows):
                    for n, v in sorted(rows, key=lambda x: -x[1]):
                        print(f"   {'>>' if is_target(n) else '  '} {n}: {v:,}")
                    append_history(b["id"], rows)
                else:
                    errors[b["id"]] = f"Lan do gan nhat loi: {err}"
                    print("   !!", err)
            browser.close()
    write_site(errors)
    print("Da dung", OUT)


if __name__ == "__main__":
    main()
