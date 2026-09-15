"""
OpenAI AI Agent for Dewey Decimal Classification (DDC) detection.
Connects to OpenAI-compatible AI Gateways / endpoints (OpenAI / 9Router / vLLM / Ollama)
using the official `openai` Python package to analyze book subjects, titles,
and descriptions, and extract validated DDC codes.
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import urllib.request
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIError, OpenAI

from database import get_setting

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_URL = "http://localhost:20128"
DEFAULT_OPENAI_MODEL = "claude-flash-3.6"


@dataclass
class SearchResult:
    code: str
    class_code: str
    subject_fa: str
    subject_en: str
    class_fa: str
    class_en: str
    score: float
    match_type: str  # "ai_agent"
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "class_code": self.class_code,
            "subject_fa": self.subject_fa,
            "subject_en": self.subject_en,
            "class_fa": self.class_fa,
            "class_en": self.class_en,
            "score": round(self.score, 4),
            "match_type": self.match_type,
            "reason": self.reason,
        }


def check_internet_access(timeout: float = 1.2) -> bool:
    """
    Rapid non-blocking check to determine if the host system has active internet access.
    Probes reliable DNS roots (Cloudflare 1.1.1.1, Google 8.8.8.8, OpenDNS).
    """
    probe_hosts = [("8.8.8.8", 53), ("1.1.1.1", 53), ("208.67.222.222", 53)]
    for host, port in probe_hosts:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except OSError:
            continue
    return False


def get_openai_config(database_path: str | None = None) -> tuple[str, str, str]:
    """
    Retrieves the OpenAI-compatible endpoint configuration:
    1. Environment variables: OPENAI_BASE_URL / OPENAI_URL
    2. Database settings: openai_url
    3. Defaults
    """
    url = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_URL")
        or get_setting("openai_url", default="", database_path=database_path)
        or DEFAULT_OPENAI_URL
    )
    key = os.environ.get("OPENAI_API_KEY") or get_setting("openai_key", default="", database_path=database_path)
    model = (
        os.environ.get("OPENAI_MODEL")
        or get_setting("openai_model", default="", database_path=database_path)
        or DEFAULT_OPENAI_MODEL
    )

    url = url.strip().rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}"

    return url, key.strip(), model.strip()


# Backward compatibility alias
get_9router_config = get_openai_config


class DeweyAIAgent:
    """
    Autonomous LLM Agent communicating via the official OpenAI Python package
    to perform semantic Dewey Decimal Classification for books, topics, and inquiries.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        database_path: str | None = None,
    ):
        self.database_path = database_path
        cfg_url, cfg_key, cfg_model = get_openai_config(database_path=database_path)
        self.base_url = (base_url or cfg_url).rstrip("/")
        self.api_key = api_key if api_key is not None else cfg_key
        self.model = model or cfg_model

    @property
    def api_base_url(self) -> str:
        """Returns normalized OpenAI v1 base URL."""
        clean = self.base_url.rstrip("/")
        if not clean.endswith("/v1"):
            return f"{clean}/v1"
        return clean

    def _get_client(self, timeout: float = 10.0) -> OpenAI:
        """Instantiates an OpenAI client with the configured base_url and key."""
        return OpenAI(
            base_url=self.api_base_url,
            api_key=self.api_key if self.api_key else "not-needed",
            timeout=timeout,
        )

    def is_available(self, timeout: float = 2.0) -> bool:
        """Checks if the OpenAI-compatible AI service is reachable and responsive."""
        # 1. Try via OpenAI models list endpoint
        try:
            client = self._get_client(timeout=timeout)
            client.models.list()
            return True
        except (APIConnectionError, APIError):
            pass
        except Exception:
            pass

        # 2. Try pinging health endpoint if server provides one
        try:
            health_url = f"{self.base_url}/api/health"
            req = urllib.request.Request(health_url)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return bool(data.get("ok", False))
        except Exception:
            pass

        return False

    def detect_ddc(
        self,
        topic: str,
        author: str | None = None,
        description: str | None = None,
        timeout: float = 12.0,
    ) -> SearchResult | None:
        """
        Uses the OpenAI client to detect and classify the DDC for a topic/book.
        Requires active internet access. Validates output strictly.
        """
        from services.dewey_service import is_valid_dewey, normalize_dewey_code

        clean_topic = (topic or "").strip()
        if not clean_topic:
            return None

        # Verify internet access first
        if not check_internet_access(timeout=1.0):
            logger.warning("Internet access unavailable. Skipping AI Agent.")
            return None

        system_prompt = (
            "You are a professional library cataloging AI agent specializing in Dewey Decimal Classification (DDC / رده‌بندی دهدهی دیویی).\n"
            "Given a book topic, title, author, or description, determine the most precise DDC classification.\n"
            "You MUST reply ONLY with a valid JSON object with these exact keys:\n"
            '{\n  "dewey_code": "...",      // Valid 3-digit or decimal DDC code (e.g. "510", "530", "005.13", "891.55", "955")\n'
            '  "dewey_class": "...",     // Main category name in Persian (e.g. "علوم محض و طبیعی", "ادبیات", "فناوری")\n'
            '  "dewey_subject": "...",   // Specific subject name in Persian (e.g. "ریاضیات", "برنامه‌نویسی پایتون", "تاریخ ایران")\n'
            '  "confidence": 0.95,       // Float between 0.0 and 1.0\n'
            '  "reason": "..."           // Concise Persian explanation\n}'
        )

        user_content_parts = [f"عنوان یا موضوع: {clean_topic}"]
        if author:
            user_content_parts.append(f"پدیدآورنده: {author.strip()}")
        if description:
            user_content_parts.append(f"توضیحات: {description.strip()[:300]}")
        user_prompt = "\n".join(user_content_parts)

        try:
            client = self._get_client(timeout=timeout)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )

            if not response.choices:
                return None

            raw_content = response.choices[0].message.content or ""
            raw_content = re.sub(r"^```json\s*", "", raw_content.strip())
            raw_content = re.sub(r"\s*```$", "", raw_content.strip())

            parsed = json.loads(raw_content)
            raw_code = str(parsed.get("dewey_code", "")).strip()

            if not is_valid_dewey(raw_code, allow_empty=False):
                logger.warning(f"AI service returned invalid DDC code: {raw_code}")
                return None

            norm_code = normalize_dewey_code(raw_code) or raw_code
            main_class_code = norm_code[:1] + "00"
            subj_fa = parsed.get("dewey_subject") or "نامشخص"
            cls_fa = parsed.get("dewey_class") or "رده عمومی"
            confidence = float(parsed.get("confidence") or 0.90)
            reason = parsed.get("reason") or "تشخیص هوشمند توسط هوش مصنوعی"

            return SearchResult(
                code=norm_code,
                class_code=main_class_code,
                subject_fa=subj_fa,
                subject_en=subj_fa,
                class_fa=cls_fa,
                class_en=cls_fa,
                score=min(1.0, max(0.1, confidence)),
                match_type="ai_agent",
                reason=reason,
            )

        except Exception as ex:
            logger.warning(f"AI Agent failed to classify '{clean_topic}': {ex}")
            return None
