from datetime import date

import httpx

from job_hunter.sources import wwr

_RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>We Work Remotely</title>
    <item>
      <title>{title}</title>
      <region>{region}</region>
      <category>Programming</category>
      <type>Full-Time</type>
      <description>{description}</description>
      <pubDate>{pub_date}</pubDate>
      <guid>{link}</guid>
      <link>{link}</link>
    </item>
  </channel>
</rss>
"""


def _rss(
    title="Acme: Backend Engineer",
    region="Anywhere in the World",
    description="Job description here.",
    pub_date="Sat, 05 Sep 2026 07:31:22 +0000",
    link="https://weworkremotely.com/remote-jobs/acme-backend-engineer",
) -> str:
    return _RSS_TEMPLATE.format(title=title, region=region, description=description, pub_date=pub_date, link=link)


def _client_returning(xml_text: str) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml_text)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_jobs_maps_fields_correctly():
    client = _client_returning(_rss())
    jobs = wwr.fetch_jobs(client=client)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "Acme"
    assert job.title == "Backend Engineer"
    assert job.source == "wwr"
    assert job.remote_type == "fully_remote"
    assert job.nigeria_eligible is True
    assert job.posted_date == date(2026, 9, 5)
    assert job.url == "https://weworkremotely.com/remote-jobs/acme-backend-engineer"


def test_title_without_colon_has_no_company():
    client = _client_returning(_rss(title="Backend Engineer Opening"))
    jobs = wwr.fetch_jobs(client=client)
    assert jobs[0].company == ""
    assert jobs[0].title == "Backend Engineer Opening"


def test_restricted_region_marks_ineligible():
    client = _client_returning(_rss(region="USA Only"))
    jobs = wwr.fetch_jobs(client=client)
    assert jobs[0].nigeria_eligible is False


def test_fetch_jobs_handles_empty_feed():
    empty_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>We Work Remotely</title></channel></rss>"""
    client = _client_returning(empty_rss)
    assert wwr.fetch_jobs(client=client) == []
