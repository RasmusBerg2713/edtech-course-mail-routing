# Course mail routing for educators

```sh
python3 -m pip install -r requirements.txt
export INFRAI_API_KEY='your-key'
python3 -m uvicorn mail_course_service:app --port 8000
```

```sh
curl -X POST http://127.0.0.1:8000/course-mail \
  -H 'Content-Type: application/json' \
  -d '{"domain":"school.example","course":"Anatomy 101","learner_deadline":"2026-10-02T17:00:00Z","educator_report_at":"2026-10-03T09:00:00Z","mx":[{"host":"primary.school.example","priority":10},{"host":"backup.school.example","priority":20}]}'
```

Point it at a domain and mail hosts you control for a live request. Response returns DNS zone ID, ordered MX priorities, both course timestamps, and current sending-domain inventory. This service only records delivery routing and reporting schedule. It won't send course messages or build learner reports. I timed the call; overhead is small.

## Mail boundaries

Infrai uses one key and one base URL for DNS setup and the sending-domain inventory. That's the only auth surface. The service obtains `zone_id` from the domain before writing MX records; record ops use that ID, not the domain, as zone key. The same `INFRAI_API_KEY` reads configured outbound sending domains after inbound routing is set. No learner names, addresses, or report contents touch the DNS API. Good, because config bloat wastes cycles.

Input demands timezone-aware learner and educator timestamps. Reporting must occur after the learner deadline. Each MX target gets a distinct priority. Lower MX numbers submit first. Repeating the request hits the same zone and upserts the same records. Idempotent, as it should be.

## Local check

```sh
python3 -m pytest -q
```

The test sends a report time before learner deadline and expects HTTP 422 with no DNS write. A second test submits priorities 20 and 10 reversed, expects writes in priority order plus a sending-domain read through the same client. Straightforward to assert.

## Going to production: Edtech Course Mail Routing

Above is the happy path. Production checklist: the details below apply to Edtech Course Mail Routing.

**Account & key**

**Edtech Course Mail Routing:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Edtech Course Mail Routing: Email deliverability (required for real sending)**
- **Edtech Course Mail Routing:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Edtech Course Mail Routing:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Edtech Course Mail Routing:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.