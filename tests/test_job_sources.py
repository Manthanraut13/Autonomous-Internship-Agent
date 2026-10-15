"""
CSV <-> registry contract tests for internship_sources_autonomous_agent.csv (the
26-portal spec): order, priority classes and quotas must match what
tools/job_api.py actually registers. Plus one offline parse test per distinct
fetcher shape (RSS, HN Algolia 2-step, JSON-LD, JSON Feed, WP REST, NEXT_DATA,
HTML cards, search-API + JSON-LD) — every network seam monkeypatched, no sockets.
"""
import csv
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.job_api as ja

CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "internship_sources_autonomous_agent.csv",
)

MAIN_COUNT = 9  # CSV rows 2-10 are the Main pass; rows 11-27 are Fallback

# CSV display name -> registry slug, in CSV row order (spec rows 2-27).
CSV_ROWS = [
    ("Y Combinator Jobs", "yc"),
    ("Startup Jobs", "startupjobs"),
    ("Web Search (Google/Brave)", "websearch"),
    ("Wellfound", "wellfound"),
    ("Cutshort", "cutshort"),
    ("LinkedIn Jobs", "linkedin"),
    ("Instahyre", "instahyre"),
    ("Hirist", "hirist"),
    ("Naukri", "naukri"),
    ("Hacker News \u2013 Who is Hiring", "hn"),
    ("Remote OK", "remoteok"),
    ("Remotive", "remotive"),
    ("Himalayas", "himalayas"),
    ("We Work Remotely", "wwr"),
    ("Built In", "builtin"),
    ("Welcome to the Jungle", "wttj"),
    ("Underdog.io", "underdog"),
    ("NoDesk", "nodesk"),
    ("Remote Rocketship", "remoterocketship"),
    ("InternDoor", "interndoor"),
    ("Jobsii", "jobsii"),
    ("Greenhouse Career Pages", "greenhouse"),
    ("Lever Career Pages", "lever"),
    ("Ashby Job Boards", "ashby"),
    ("Workable", "workable"),
    ("Direct Startup Career Pages", "discovery"),
]


@pytest.fixture(autouse=True)
def clean_module_caches():
    """Fetchers memoize boards/sitemaps/negative results per process — reset."""
    ja._NEGATIVE_CACHE.clear()
    ja._NODESK_SITEMAP_CACHE.clear()
    ja._NODESK_DETAIL_CACHE.clear()
    ja._RRS_CATEGORY_CACHE.clear()
    ja._BOARD_CACHE.clear()
    ja._DIRECTORY_CACHE.clear()
    yield


# ── CSV <-> registry contract ────────────────────────────────────────────────

def test_csv_rows_match_spec_order():
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 26
    assert [r["Website / Source"] for r in rows] == [n for n, _ in CSV_ROWS]
    priorities = [r["Priority"] for r in rows]
    assert priorities[:MAIN_COUNT] == ["Main"] * MAIN_COUNT
    assert priorities[9:21] == ["Fallback"] * 12
    assert priorities[21:25] == ["Fallback/Direct ATS"] * 4
    assert priorities[25:] == ["Fallback/Discovery"]


def test_registry_order_mirrors_csv():
    main = ja.get_scraper_platforms()
    fallback = ja.get_fallback_platforms()
    assert [p["source"] for p in main] == [slug for _, slug in CSV_ROWS[:MAIN_COUNT]]
    assert [p["source"] for p in fallback] == [slug for _, slug in CSV_ROWS[MAIN_COUNT:]]


def test_every_portal_registered_with_positive_quota_and_callable():
    all_platforms = ja.get_scraper_platforms() + ja.get_fallback_platforms()
    assert len(all_platforms) == 26
    assert len({p["source"] for p in all_platforms}) == 26
    for p in all_platforms:
        assert callable(p["fn"]), p["source"]
        assert isinstance(p["quota"], int) and p["quota"] > 0, p["source"]
        assert p["name"], p["source"]
    assert set(ja.PLATFORM_QUOTAS) == {slug for _, slug in CSV_ROWS}
    # The Main pass alone must be able to reach the 25-opening target
    assert sum(p["quota"] for p in ja.get_scraper_platforms()) >= 25


# ── parse_job_date branches (root-cause: ISO + RFC822) ──────────────────────

def test_parse_job_date_branches():
    naive = ja.parse_job_date("2026-09-22t06:13:05.896001")
    assert naive is not None and naive.tzinfo is not None  # naive ISO -> UTC
    aware = ja.parse_job_date("2026-10-12t20:12:51.707+00:00")
    assert aware is not None and aware.microsecond == 707000
    rfc = ja.parse_job_date("Mon, 12 Oct 2026 03:02:30 +0000")
    assert rfc is not None and rfc.day == 12
    assert ja.parse_job_date("2026-10-12") is not None
    assert ja.parse_job_date("not a date") is None
    assert ja.parse_job_date(None) is None


# ── one offline parse test per distinct fetch shape ──────────────────────────

def test_wwr_rss_shape(monkeypatch):
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>We Work Remotely: Programming</title>
<item>
  <title>Acme Corp: AI Engineer Intern</title>
  <link>https://weworkremotely.com/remote-jobs/acme-ai</link>
  <description>&lt;p&gt;Build LLM tooling for teams.&lt;/p&gt;</description>
  <pubDate>Mon, 12 Oct 2026 03:02:30 +0000</pubDate>
</item>
<item>
  <title>Globex: ML Engineer</title>
  <link>https://weworkremotely.com/remote-jobs/globex-ml</link>
  <description>&lt;p&gt;Remote ML role&lt;/p&gt;</description>
  <pubDate>garbage-date</pubDate>
</item>
</channel></rss>"""
    monkeypatch.setattr(ja, "_get_text", lambda url, **kw: rss)
    jobs = ja.fetch_wwr_jobs("AI Engineer", limit=5)
    assert len(jobs) == 2
    first = jobs[0]
    assert first["company"] == "Acme Corp"  # 'Company: Role' colon split
    assert first["title"] == "AI Engineer Intern"
    assert first["source"] == "wwr"
    assert first["link"] == "https://weworkremotely.com/remote-jobs/acme-ai"
    assert "Build LLM tooling" in first["description"]
    assert first["posted_at"] is not None  # RFC822 pubDate parsed
    assert jobs[1]["posted_at"] is None  # garbage date -> never fabricated


def test_hn_two_step_algolia(monkeypatch):
    stories = {"hits": [{"objectID": "400000",
                         "title": "Ask HN: Who is hiring? (October 2026)"}]}
    comments = {"hits": [
        {"objectID": "400001",
         "comment_text": "<p>Acme Labs</p><p>AI Engineer Intern</p><p>Bengaluru, India</p>",
         "created_at": "2026-10-12T05:00:00Z"},
        {"objectID": "400002",
         "comment_text": 'Zeta | AI Engineer | Remote (India) | '
                         '<a href="https://zeta.example/apply">apply</a>',
         "created_at": "2026-10-11T05:00:00Z"},
    ]}

    def fake_get_json(url, params=None, **kw):
        return stories if "who is hiring" in (params or {}).get("query", "") else comments

    monkeypatch.setattr(ja, "_get_json", fake_get_json)
    jobs = ja.fetch_hn_jobs("AI Engineer", limit=5)
    assert len(jobs) == 2
    para, pipe = jobs  # paragraph-format comment, pipe-format comment
    assert para["company"] == "Acme Labs"
    assert para["title"] == "AI Engineer Intern"
    assert para["location"] == "Bengaluru, India"
    assert para["link"] == "https://news.ycombinator.com/item?id=400001"
    assert para["posted_at"] is not None
    assert pipe["company"] == "Zeta"
    assert pipe["title"] == "AI Engineer"
    assert pipe["location"] == "Remote (India)"
    assert pipe["link"] == "https://zeta.example/apply"
    assert pipe["source"] == "hn"


def test_nodesk_json_ld_unquoted_attrs(monkeypatch):
    sitemap = ("<urlset><url><loc>https://nodesk.co/remote-jobs/ai-engineer/</loc>"
               "</url></urlset>")
    page = """<html><head><script type=application/ld+json>
 {"@type": "JobPosting", "title": "AI Engineer",
  "description": "<p>Build AI agents remotely</p>",
  "hiringOrganization": {"name": "Acme"},
  "jobLocation": {"address": {"addressLocality": "Bengaluru", "addressCountry": "IN"}},
  "datePosted": "2026-10-10", "url": "https://nodesk.co/remote-jobs/ai-engineer/"}
</script></head><body></body></html>"""

    def fake_get_text(url, **kw):
        return sitemap if url.endswith(".xml") else page

    monkeypatch.setattr(ja, "_get_text", fake_get_text)
    jobs = ja.fetch_nodesk_jobs("AI Engineer", limit=5)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["company"] == "Acme"
    assert job["title"] == "AI Engineer"
    assert job["location"] == "Bengaluru, IN"
    assert job["posted_at"] is not None
    assert job["source"] == "nodesk"


def test_interndoor_json_feed(monkeypatch):
    feed = {"items": [{
        "title": "Machine Learning Intern",
        "content_text": "Work on recommender systems in Bengaluru. Stipend offered.",
        "url": "https://interndoor.com/jobs/ml-intern",
        "date_published": "2026-10-12T01:00:00Z",
        "authors": [{"name": "Acme Analytics"}],
    }]}
    monkeypatch.setattr(ja, "_get_json", lambda url, **kw: feed)
    jobs = ja.fetch_interndoor_jobs("Machine Learning", limit=5)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["company"] == "Acme Analytics"
    assert job["location"] == "Bengaluru"  # extracted + title-cased from content
    assert job["posted_at"] is not None
    assert job["source"] == "interndoor"


def test_jobsii_wordpress_rest(monkeypatch):
    data = [{
        "title": {"rendered": "AI Intern &#8211; WFH"},
        "content": {"rendered": "<p>Build LLM features</p>"},
        "link": "https://jobsii.com/job/ai-intern-wfh/",
        "date": "2026-10-12T10:00:00",
        "acf": {"company_name": "Acme Pvt Ltd",
                "job_url": "https://acme.example/careers/1",
                "location": "Remote, India"},
    }]
    monkeypatch.setattr(ja, "_get_json", lambda url, **kw: data)
    jobs = ja.fetch_jobsii_jobs("AI Intern", limit=5)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["title"] == "AI Intern \u2013 WFH"  # HTML entity unescaped
    assert job["company"] == "Acme Pvt Ltd"
    assert job["apply_url"] == "https://acme.example/careers/1"
    assert job["location"] == "Remote, India"
    assert job["posted_at"] is not None


def test_remoterocketship_next_data(monkeypatch):
    payload = {"props": {"pageProps": {"initialJobOpenings": [{
        "roleTitle": "AI Engineer Intern",
        "company": {"name": "Acme Cloud"},
        "location": "Bengaluru, India",
        "jobDescriptionSummary": "Build AI agents",
        "created_at": "2026-10-11T10:00:00.000+00:00",
        "url": "https://jobs.example/acme/1",
        "techStack": ["python", "llm"],
    }]}}}
    page = ('<html><body><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(payload) + "</script></body></html>")
    monkeypatch.setattr(ja, "_get_text", lambda url, **kw: page)
    monkeypatch.setattr(ja, "_RRS_CATEGORIES", ["software-engineer"])
    jobs = ja.fetch_remoterocketship_jobs("AI Engineer", limit=5)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["company"] == "Acme Cloud"  # company object unwrapped
    assert job["title"] == "AI Engineer Intern"
    assert job["location"] == "Bengaluru, India"
    assert job["posted_at"] is not None
    assert job["source"] == "remoterocketship"


def test_builtin_html_cards(monkeypatch):
    pytest.importorskip("bs4")
    page = ('<div class="job-card">'
            '<a href="/job/ai-engineer-intern/123">AI Engineer Intern</a>'
            " <span>Gurugram, India</span></div>")
    monkeypatch.setattr(ja, "_get_text", lambda url, **kw: page)
    jobs = ja.fetch_builtin_jobs("AI Engineer", limit=5)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["title"] == "AI Engineer Intern"
    assert job["link"] == "https://builtin.com/job/ai-engineer-intern/123"
    assert job["location"] == "India"  # country evidence wins over city
    assert job["source"] == "builtin"


# ── Web Search: provider chain + JSON-LD-only harvest ─────────────────────────

def _jp_page(title="AI Engineer Intern", company="Acme AI"):
    return ('<html><head><script type="application/ld+json">'
            '{"@type":"JobPosting","title":"' + title + '",'
            '"hiringOrganization":{"name":"' + company + '"},'
            '"jobLocation":{"address":{"addressLocality":"Bengaluru",'
            '"addressCountry":"India"}},'
            '"datePosted":"2026-10-14",'
            '"description":"&lt;p&gt;Build LLM agents and automation.&lt;/p&gt;"'
            "}</script></head><body></body></html>")


def _set_websearch_keys(monkeypatch, google="", cx="", brave=""):
    monkeypatch.setattr(ja.settings, "google_cse_api_key", google)
    monkeypatch.setattr(ja.settings, "google_cse_cx", cx)
    monkeypatch.setattr(ja.settings, "brave_search_api_key", brave)


def test_websearch_google_cse_harvests_real_jobposting(monkeypatch):
    _set_websearch_keys(monkeypatch, google="k", cx="cx")
    cse = {"items": [{"link": "https://boards.example/acme/jobs/1",
                      "title": "AI Engineer Intern"}]}
    monkeypatch.setattr(ja, "_get_json", lambda url, params=None, **kw: cse)
    monkeypatch.setattr(ja, "_get_text", lambda url, **kw: _jp_page())
    jobs = ja.fetch_websearch_jobs("AI Engineer", limit=5)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["title"] == "AI Engineer Intern"
    assert job["company"] == "Acme AI"
    assert job["location"] == "Bengaluru, India"
    assert job["link"] == "https://boards.example/acme/jobs/1"
    assert job["source"] == "websearch"
    assert job["posted_at"] is not None
    assert "LLM agents" in job["description"]


def test_websearch_brave_fallback_when_google_unconfigured(monkeypatch):
    _set_websearch_keys(monkeypatch, brave="b-key")
    brave = {"web": {"results": [{"url": "https://boards.example/acme/jobs/2",
                                  "title": "AI Intern"}]}}
    monkeypatch.setattr(ja, "_get_json", lambda url, params=None, **kw: brave)
    monkeypatch.setattr(ja, "_get_text", lambda url, **kw: _jp_page())
    jobs = ja.fetch_websearch_jobs("AI", limit=5)
    assert len(jobs) == 1 and jobs[0]["source"] == "websearch"


def test_websearch_drops_results_without_jobposting_jsonld(monkeypatch):
    """A search hit that is not a real structured posting must never ship."""
    _set_websearch_keys(monkeypatch, google="k", cx="cx")
    cse = {"items": [{"link": "https://blog.example/post", "title": "AI news"}]}
    monkeypatch.setattr(ja, "_get_json", lambda url, params=None, **kw: cse)
    monkeypatch.setattr(ja, "_get_text",
                        lambda url, **kw: "<html><body><p>blog post, no job</p></body></html>")
    assert ja.fetch_websearch_jobs("AI", limit=5) == []


def test_websearch_unconfigured_returns_empty_and_caches(monkeypatch):
    _set_websearch_keys(monkeypatch)  # no keys at all
    monkeypatch.setattr(
        ja, "_get_json",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("provider called without keys")))
    assert ja.fetch_websearch_jobs("AI", limit=5) == []
    assert ja._recently_empty("websearch")  # negative-cached for the run
    assert ja.fetch_websearch_jobs("AI", limit=5) == []  # cached -> no re-attempt


# ── JD enrichment: the scoring root-cause fix ─────────────────────────────────

def _fake_requests(monkeypatch, jdf, page):
    class FakeResp:
        status_code = 200
        text = page

    class FakeRequests:
        @staticmethod
        def get(*a, **kw):
            return FakeResp()

    monkeypatch.setattr(jdf, "requests", FakeRequests)


def test_jd_fetcher_prefers_jobposting_jsonld(monkeypatch):
    pytest.importorskip("bs4")
    import tools.jd_fetcher as jdf
    page = ('<html><head>'
            '<meta property="og:description" content="short og"/>'
            '<script type="application/ld+json">'
            '{"@type":"JobPosting","description":"<p>Build LLM agents with '
            "LangChain: RAG pipelines, tool-calling agents, evals and "
            "production MLOps for a Bengaluru AI startup. Python required.</p>\"}"
            "</script></head><body><div>junk nav text long enough that the old "
            "selector path would have picked it as the description instead</div></body></html>")
    _fake_requests(monkeypatch, jdf, page)
    text = jdf.fetch_full_job_description("https://example.com/j/1")
    assert text is not None and "Build LLM agents" in text


def test_jd_fetcher_og_description_fallback(monkeypatch):
    pytest.importorskip("bs4")
    import tools.jd_fetcher as jdf
    og = ("Build LLM agents in Python with LangChain and RAG pipelines. " * 4).strip()
    page = ('<html><head><meta property="og:description" content="' + og + '"/>'
            "</head><body><script>var x = 1;</script></body></html>")
    _fake_requests(monkeypatch, jdf, page)
    text = jdf.fetch_full_job_description("https://example.com/j/2")
    assert text is not None and text.startswith("Build LLM agents")


def test_jd_fetcher_returns_none_when_no_real_content(monkeypatch):
    pytest.importorskip("bs4")
    import tools.jd_fetcher as jdf
    _fake_requests(monkeypatch, jdf, "<html><body><p>Too short.</p></body></html>")
    assert jdf.fetch_full_job_description("https://example.com/j/3") is None
