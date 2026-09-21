"""Best-effort contact discovery from a business's own public website:
email address, Instagram profile link, Facebook profile link."""

import re
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config

logger = config.get_logger(__name__)

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CANDIDATE_PATHS = ["", "/contact", "/contact-us", "/about", "/about-us"]
USER_AGENT = "LeadGenAgent/1.0 (+best-effort contact info lookup)"

# Common filename extensions / false-positive domains to discard from regex matches.
JUNK_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")

# Path fragments that indicate a share widget/login page rather than the
# business's own profile — skipped when scanning for social links.
FACEBOOK_EXCLUDE = ("sharer", "share.php", "plugins", "policy", "policies", "login", "dialog", "tr?", "l.php")
INSTAGRAM_EXCLUDE = ("explore", "accounts/login", "/p/", "/reel/", "/tv/", "developer")


def _robots_allowed(base_url: str, path: str) -> bool:
    try:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(USER_AGENT, urljoin(base_url, path))
    except Exception:
        # If robots.txt can't be fetched/parsed, default to allowing the fetch.
        return True


def _extract_email(soup: BeautifulSoup) -> str | None:
    for link in soup.select("a[href^='mailto:']"):
        addr = link["href"].split("mailto:", 1)[1].split("?")[0].strip()
        if addr:
            return addr

    text = soup.get_text(" ")
    for match in EMAIL_PATTERN.findall(text):
        if not match.lower().endswith(JUNK_SUFFIXES):
            return match

    return None


def _extract_social_link(soup: BeautifulSoup, base_url: str, domain: str, exclude: tuple) -> str | None:
    for link in soup.select("a[href]"):
        href = urljoin(base_url, link["href"])
        parsed = urlparse(href)
        if domain not in parsed.netloc.lower():
            continue
        if parsed.path in ("", "/"):
            continue
        if any(bad in href.lower() for bad in exclude):
            continue
        return href.split("?")[0]
    return None


def gather_contact_info(website_url: str) -> dict:
    """Scans the homepage and common contact/about pages of a business
    website for an email address and Instagram/Facebook profile links.
    Best-effort only — any field may come back None.

    Returns: {"email": str | None, "instagram": str | None, "facebook": str | None}
    """
    info = {"email": None, "instagram": None, "facebook": None}
    if not website_url:
        return info

    for path in CANDIDATE_PATHS:
        if all(info.values()):
            break

        if not _robots_allowed(website_url, path):
            logger.info("robots.txt disallows %s%s, skipping", website_url, path)
            continue

        url = urljoin(website_url, path)
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=config.REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.info("Could not fetch %s: %s", url, exc)
            time.sleep(config.SCRAPE_DELAY)
            continue

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            if not info["email"]:
                info["email"] = _extract_email(soup)
            if not info["instagram"]:
                info["instagram"] = _extract_social_link(soup, url, "instagram.com", INSTAGRAM_EXCLUDE)
            if not info["facebook"]:
                info["facebook"] = _extract_social_link(soup, url, "facebook.com", FACEBOOK_EXCLUDE)

        time.sleep(config.SCRAPE_DELAY)

    return info
