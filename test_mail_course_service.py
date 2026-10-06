from unittest.mock import Mock

from fastapi.testclient import TestClient

import mail_course_service as service


def test_deadline_boundary_prevents_dns_writes(monkeypatch):
    client = Mock()
    monkeypatch.setattr(service, "MailClient", lambda key: client)
    monkeypatch.setenv("INFRAI_API_KEY", "test-key")
    response = TestClient(service.app).post("/course-mail", json={
        "domain": "school.example", "course": "Anatomy 101",
        "learner_deadline": "2026-10-02T17:00:00Z",
        "educator_report_at": "2026-10-02T16:00:00Z",
        "mx": [{"host": "mail.school.example", "priority": 10}],
    })
    assert response.status_code == 422
    client.zone.assert_not_called()


def test_mx_order_and_shared_client(monkeypatch):
    client = Mock()
    client.zone.return_value = "zone-123"
    client.sending_domains.return_value = {"domains": []}
    monkeypatch.setattr(service, "MailClient", lambda key: client)
    monkeypatch.setenv("INFRAI_API_KEY", "test-key")
    response = TestClient(service.app).post("/course-mail", json={
        "domain": "school.example", "course": "Anatomy 101",
        "learner_deadline": "2026-10-02T17:00:00Z",
        "educator_report_at": "2026-10-03T09:00:00Z",
        "mx": [
            {"host": "backup.school.example", "priority": 20},
            {"host": "primary.school.example", "priority": 10},
        ],
    })
    assert response.status_code == 200
    assert response.json()["mx_priorities"] == [10, 20]
    assert [call.args[3] for call in client.mx.call_args_list] == [10, 20]
    client.sending_domains.assert_called_once_with()
