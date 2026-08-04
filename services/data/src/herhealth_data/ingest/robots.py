"""robots.txt compliance, enforced rather than promised.

Every fetch is checked against the origin's robots.txt before the request is
made. A disallowed URL is refused the same way a licence-barred one is: no
request, an ``excluded`` outcome, and a reason recorded.

This exists because the alternative is a person remembering to check, and the
project has already been through one round of "we said we wouldn't" — which is
exactly the kind of promise that decays. Making it a code path means the rule
holds whoever adds the next target.

Path matching is case-sensitive, per RFC 9309 and per stdlib ``robotparser``.
That matters here: nhs.uk disallows ``/Conditions/`` with a capital C while its
live URLs are lowercase ``/conditions/``. We follow the standard rather than
guessing at intent in either direction — and because the check is recorded in
the fetch record, whichever way it resolves is visible rather than assumed.

One robots.txt is fetched per host and cached for the run. A host that does not
serve one is treated as allowing everything, which is what the standard says.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from herhealth_data.ingest.config import Transport

__all__ = ["RobotsPolicy", "robots_url_for"]


def robots_url_for(url: str) -> str:
    """The robots.txt that governs a URL."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))


@dataclass
class RobotsPolicy:
    """Caches one robots.txt per host and answers allow/deny against it."""

    transport: Transport
    _parsers: dict[str, RobotFileParser | None] = field(default_factory=dict)

    def _parser_for(self, url: str) -> RobotFileParser | None:
        host = urlsplit(url).netloc
        if host in self._parsers:
            return self._parsers[host]

        parser: RobotFileParser | None = None
        try:
            status, body = self.transport(robots_url_for(url), "*")
        except RuntimeError:
            # Unreachable robots.txt is not permission to crawl, but neither is
            # it a denial. Treated as absent, which the standard allows.
            status, body = 0, b""

        if status == 200 and body:
            parser = RobotFileParser()
            parser.parse(body.decode("utf-8", errors="replace").splitlines())

        self._parsers[host] = parser
        return parser

    def is_allowed(self, url: str, user_agent: str) -> bool:
        """Whether robots.txt permits fetching this URL with this agent."""
        parser = self._parser_for(url)
        if parser is None:
            return True
        return bool(parser.can_fetch(user_agent, url))

    def reason_if_disallowed(self, url: str, user_agent: str) -> str | None:
        """None if permitted, otherwise a message naming the governing file."""
        if self.is_allowed(url, user_agent):
            return None
        return f"robots.txt disallows this path: {robots_url_for(url)}"
