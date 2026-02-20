"""Provider registry for Statuspage-based status pages."""

from pydantic import BaseModel


class StatusPageProvider(BaseModel):
    key: str
    name: str
    base_url: str
    page_id: str
    enabled: bool = True

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/api/v2"


# Verified Atlassian Statuspage instances with real page IDs.
# To add a new provider, append to this list — the system handles the rest.
PROVIDERS: list[StatusPageProvider] = [
    StatusPageProvider(
        key="openai",
        name="OpenAI",
        base_url="https://status.openai.com",
        page_id="01JMDK9XYNY6RXSED6SDWW50WY",
    ),
    StatusPageProvider(
        key="github",
        name="GitHub",
        base_url="https://www.githubstatus.com",
        page_id="kctbh9vrtdwd",
    ),
    StatusPageProvider(
        key="cloudflare",
        name="Cloudflare",
        base_url="https://www.cloudflarestatus.com",
        page_id="yh6f0r4529hb",
    ),
    StatusPageProvider(
        key="atlassian",
        name="Atlassian",
        base_url="https://status.atlassian.com",
        page_id="0f54fx204jpt",
    ),
    StatusPageProvider(
        key="datadog",
        name="Datadog",
        base_url="https://status.datadoghq.com",
        page_id="1k6wzpspjf99",
    ),
    StatusPageProvider(
        key="twilio",
        name="Twilio",
        base_url="https://status.twilio.com",
        page_id="gpkpyklzq55q",
    ),
    StatusPageProvider(
        key="vercel",
        name="Vercel",
        base_url="https://www.vercel-status.com",
        page_id="lvglq8h0mdyh",
    ),
    StatusPageProvider(
        key="linear",
        name="Linear",
        base_url="https://linearstatus.com",
        page_id="01GYJ3SH6BPHBR7V0GQAW4GTM0",
    ),
    StatusPageProvider(
        key="hashicorp",
        name="HashiCorp",
        base_url="https://status.hashicorp.com",
        page_id="01K7FBWXHZPP52EWA3EGJ2SNVA",
    ),
    StatusPageProvider(
        key="notion",
        name="Notion",
        base_url="https://www.notion-status.com",
        page_id="kgl53swp0yg1",
    ),
]

_by_key: dict[str, StatusPageProvider] = {p.key: p for p in PROVIDERS}
_by_page_id: dict[str, StatusPageProvider] = {p.page_id: p for p in PROVIDERS}


def get_provider(key: str) -> StatusPageProvider | None:
    return _by_key.get(key)


def get_enabled_providers() -> list[StatusPageProvider]:
    return [p for p in PROVIDERS if p.enabled]


def get_provider_by_page_id(page_id: str) -> StatusPageProvider | None:
    return _by_page_id.get(page_id)
