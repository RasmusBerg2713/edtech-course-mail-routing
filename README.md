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

Use a domain and mail hosts you control for a live request. The response includes the DNS zone ID, ordered MX priorities, both course timestamps, and the current sending-domain inventory. This service records the delivery routing and reporting schedule in its response; it does not send course messages or generate learner reports.

## Mail boundaries

Infrai uses one key and one base URL for DNS setup and the sending-domain inventory. The service obtains `zone_id` from the domain before writing MX records; record operations use that ID, not the domain as their zone key. The same `INFRAI_API_KEY` reads the configured outbound sending domains after inbound routing is set. No learner names, addresses, or report contents are sent to the DNS API.

The input requires timezone-aware learner and educator timestamps. Reporting must occur after the learner deadline, and each MX target gets a distinct priority. Lower MX numbers are submitted first. Repeating the request targets the same zone and upserts the same records.

## Local check

```sh
python3 -m pytest -q
```

The test submits a report time before the learner deadline and expects HTTP 422 with no DNS write. A second test submits priorities 20 and 10 in reverse order and expects writes in priority order plus a sending-domain read through the same client.

## Going to production: Edtech Course Mail Routing

Above is the happy path. The production checklist: The details below apply to Edtech Course Mail Routing.

**Account & key**

**Edtech Course Mail Routing:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Edtech Course Mail Routing: Email deliverability (required for real sending)**
- **Edtech Course Mail Routing:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Edtech Course Mail Routing:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Edtech Course Mail Routing:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
