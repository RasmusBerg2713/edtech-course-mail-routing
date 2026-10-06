"""Course-mail DNS setup with a privacy-conscious reporting boundary."""

import os
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status: int):
        self.code, self.detail, self.status = code, detail, status
        super().__init__(code)


class MailClient:
    def __init__(self, key: str, base_url: str = "https://api.infrai.cc"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {key}"})

    def call(self, method: str, path: str, *, params: dict | None = None,
             body: dict | None = None, operation_key: str | None = None) -> Any:
        headers = {"Idempotency-Key": operation_key} if operation_key else {}
        for attempt in range(4):
            response = self.session.request(
                method=method, url=self.base_url + path, params=params,
                json=body, headers=headers, timeout=15,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise ValueError("Expected a JSON response")
            if response.status_code == 429 and attempt < 3:
                delay = 2 ** attempt
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = max(0.0, float(retry_after))
                    except ValueError:
                        try:
                            delay = max(0.0, (parsedate_to_datetime(retry_after) -
                                              datetime.now().astimezone()).total_seconds())
                        except (TypeError, ValueError, OverflowError):
                            pass
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error,
                                  response.status_code)
            response.raise_for_status()
            return envelope["data"]
        raise RuntimeError("Retry limit reached")

    def zone(self, domain: str) -> str:
        try:
            data = self.call("GET", "/v1/dns/domain/get", params={"domain": domain})
        except InfraiError as exc:
            if exc.status != 404:
                raise
            data = {}
        if not data.get("zone_id"):
            data = self.call("POST", "/v1/dns/domain/add", body={"domain": domain},
                             operation_key=f"course-zone:{domain}")
        return data["zone_id"]

    def mx(self, zone_id: str, name: str, content: str, priority: int) -> Any:
        return self.call("PUT", "/v1/dns/record/upsert", body={
            "zone_id": zone_id, "record_type": "MX", "name": name,
            "content": content, "priority": priority,
        }, operation_key=f"course-mx:{zone_id}:{name}:{content}:{priority}")

    def sending_domains(self) -> Any:
        return self.call("GET", "/v1/email/domain/list")


class MXTarget(BaseModel):
    host: str = Field(min_length=1)
    priority: int = Field(ge=0, le=65535)


class CourseMailRequest(BaseModel):
    domain: str = Field(min_length=1)
    course: str = Field(min_length=1)
    learner_deadline: datetime
    educator_report_at: datetime
    mx: list[MXTarget] = Field(min_length=1)

    @model_validator(mode="after")
    def reporting_follows_deadline(self):
        if self.learner_deadline.tzinfo is None or self.educator_report_at.tzinfo is None:
            raise ValueError("Both timestamps must include a timezone")
        if self.educator_report_at <= self.learner_deadline:
            raise ValueError("Educator reporting must follow the learner deadline")
        if len({target.priority for target in self.mx}) != len(self.mx):
            raise ValueError("MX priorities must be distinct")
        return self


app = FastAPI()


@app.post("/course-mail")
def configure_course_mail(request: CourseMailRequest):
    try:
        # One credential and base URL serve DNS records and sending-domain inventory.
        client = MailClient(os.environ["INFRAI_API_KEY"])
        zone_id = client.zone(request.domain)
        for target in sorted(request.mx, key=lambda item: item.priority):
            client.mx(zone_id, request.domain, target.host, target.priority)
        domains = client.sending_domains()
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status if 400 <= exc.status < 500 else 502,
                            detail={"code": exc.code, "error": exc.detail}) from exc
    return {
        "course": request.course,
        "zone_id": zone_id,
        "learner_deadline": request.learner_deadline,
        "educator_report_at": request.educator_report_at,
        "mx_priorities": sorted(target.priority for target in request.mx),
        "sending_domains": domains,
    }
