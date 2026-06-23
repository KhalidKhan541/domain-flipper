"""
Free Domain Scraper — adapted from agent-os scraper pattern.
Uses simple HTTP requests with proper User-Agent headers.
No Playwright, no API keys, completely free.
"""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from src.feeds.quality_filter import filter_domains
from src.utils import setup_logger

DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.(com|io|ai|co|net|org|dev|app)$"
)

PREMIUM_TLDS = {"com", "io", "ai", "co", "net", "org", "dev", "app"}

# Massive exclude list — known corporate/tech domains that are NOT for sale
EXCLUDE_DOMAINS: set[str] = {
    # === BIG TECH ===
    "google.com", "googleapis.com", "gstatic.com", "google-analytics.com",
    "googletagmanager.com", "googlesyndication.com", "googletagservices.com",
    "googleadservices.com", "doubleclick.net", "youtube.com", "youtu.be",
    "facebook.com", "facebook.net", "fbcdn.net", "instagram.com",
    "twitter.com", "x.com", "t.co", "tiktok.com", "tiktokcdn.com",
    "apple.com", "icloud.com", "microsoft.com", "live.com", "office.com",
    "office365.com", "azure.com", "bing.com", "msn.com", "skype.com",
    "linkedin.com", "licdn.com", "slidebean.com",
    "amazon.com", "amazonaws.com", "cloudfront.net", "aws.amazon.com",
    "netflix.com", "nflxvideo.net", "nflximg.net",
    "spotify.com", "soundcloud.com",
    "slack.com", "slack-edge.com",
    "salesforce.com", "force.com",
    "adobe.com", "typekit.com",
    "oracle.com", "java.com",
    "ibm.com",
    "intel.com",
    "cisco.com",
    "samsung.com",
    "huawei.com",
    "sony.com",

    # === SOCIAL MEDIA ===
    "reddit.com", "redditstatic.com", "redditmedia.com", "redd.it",
    "pinterest.com", "pinimg.com",
    "snapchat.com", "snap.com",
    "telegram.org", "t.me",
    "whatsapp.com", "whatsapp.net",
    "discord.com", "discord.gg", "discordapp.com",
    "twitch.tv", "jtvnw.net",
    "vimeo.com",
    "dailymotion.com",
    "medium.com",
    "substack.com",
    "quora.com",
    "tumblr.com",
    "flickr.com",
    "imgur.com",
    "giphy.com",
    "9gag.com",

    # === DOMAIN/HOSTING/REGISTRAR ===
    "godaddy.com", "domains.godaddy.com",
    "namecheap.com", "namesilo.com",
    "dynadot.com", "porkbun.com",
    "cloudflare.com", "cloudflare-dns.com",
    "hover.com", "name.com",
    "google.domains", "domains.google",
    "amazon.route53.com",
    "ovh.com", "hetzner.com",
    "digitalocean.com", "linode.com",
    "vultr.com",
    "hostgator.com", "bluehost.com",
    "siteground.com", "hostinger.com",
    "squarespace.com", "wix.com",
    "weebly.com", "shopify.com",
    "wordpress.com", "wordpress.org", "wp.com",
    "blogspot.com", "blogger.com",
    "godaddy.com",
    "markmonitor.com", "MarkMonitor Inc.",
    "SafeNames Ltd.", "Gandi SAS",
    "pair Networks, Inc.", "pair Domains",
    "DropCatch.com", "NameJet.com",
    "SnapNames.com", "Sedo.com",
    "Afternic.com", "Dan.com",
    "Flippa.com",
    "escrow.com", "Escrow.com",
    "hugedomains.com", "HugeDomains.com",

    # === CDN / ANALYTICS / TRACKING ===
    "cloudfront.net", "akamai.net", "akamaihd.net", "akamaiedge.net",
    "fastly.net", "fastly.com",
    "stackpath.com", "maxcdn.com",
    "bootstrapcdn.com", "cdnjs.cloudflare.com",
    "unpkg.com", "jsdelivr.net",
    "google-analytics.com", "googletagmanager.com",
    "hotjar.com", "mixpanel.com",
    "segment.com", "amplitude.com",
    "heap.io", "fullstory.com",
    "sentry.io", "bugsnag.com",
    "newrelic.com", "nr-data.net",
    "datadoghq.com",
    "intercom.io", "intercom.com",
    "drift.com",
    "hubspot.com", "hs-scripts.com",
    "marketo.com", "marketo.net",
    "pardot.com",
    "salesforce.com",

    # === PAYMENTS / FINANCE ===
    "stripe.com", "stripe.network",
    "paypal.com", "paypal.me",
    "square.com", "squareup.com",
    "braintreepayments.com",
    "adyen.com",
    "checkout.com",
    "coinbase.com",
    "binance.com",
    "kraken.com",
    "bitstamp.net",

    # === DEV TOOLS ===
    "github.com", "github.io", "githubapp.com", "githubassets.com",
    "gitlab.com",
    "bitbucket.org",
    "atlassian.com", "atlassian.net",
    "jira.com", "confluence.com",
    "stackoverflow.com", "stackexchange.com",
    "npmjs.com", "npmjs.org",
    "pypi.org",
    "docker.com", "docker.io",
    "heroku.com", "herokuapp.com",
    "vercel.com", "zeit.co",
    "netlify.com", "netlify.app",
    "railway.app",
    "render.com",
    "fly.io",
    "supabase.com",
    "firebase.com", "firebaseio.com",
    "mongodb.com", "mongodbatlas.com",
    "redis.com", "redis.io",
    "elastic.co", "elasticsearch.com",
    "snowflake.com",
    "databricks.com",
    "figma.com",
    "canva.com",
    "notion.so",
    "airtable.com",
    "zapier.com",
    "ifttt.com",

    # === NEWS / MEDIA ===
    "nytimes.com", "washingtonpost.com",
    "bbc.com", "bbc.co.uk",
    "cnn.com",
    "reuters.com",
    "bloomberg.com",
    "wsj.com",
    "theguardian.com",
    "medium.com",
    "huffpost.com",
    "vice.com",
    "buzzfeed.com",
    "mashable.com",
    "techcrunch.com", "techcrunch.com",
    "theverge.com",
    "arstechnica.com",
    "wired.com",
    "engadget.com",
    "gizmodo.com",
    "zdnet.com",
    "cnet.com",
    "mashable.com",

    # === E-COMMERCE ===
    "ebay.com", "ebaystatic.com",
    "etsy.com",
    "walmart.com",
    "target.com",
    "bestbuy.com",
    "aliexpress.com", "alibaba.com",
    "wish.com",
    "shopify.com",
    "bigcommerce.com",
    "woocommerce.com",
    "magento.com",

    # === GAMING ===
    "steampowered.com", "steamcommunity.com",
    "epicgames.com",
    "riotgames.com",
    "blizzard.com",
    "ea.com",
    "ubisoft.com",
    "playstation.com", "psn.com",
    "xbox.com", "xboxlive.com",
    "nintendo.com",
    "twitch.tv",

    # === TRAVEL ===
    "booking.com",
    "airbnb.com", "airbnbstatic.com",
    "tripadvisor.com",
    "expedia.com",
    "hotels.com",
    "kayak.com",
    "skyscanner.com",
    "uber.com",
    "lyft.com",

    # === FOOD / DELIVERY ===
    "doordash.com",
    "ubereats.com",
    "grubhub.com",
    "postmates.com",
    "instacart.com",
    "mealmaster.com",

    # === EDUCATION ===
    "coursera.com",
    "udemy.com",
    "edx.org",
    "khanacademy.org",
    "duolingo.com",
    "leetcode.com",
    "hackerrank.com",
    "codecademy.com",
    "freecodecamp.org",

    # === HEALTH ===
    "webmd.com",
    "mayoclinic.org",
    "healthline.com",
    "medicalnewstoday.com",
    "zocdoc.com",
    "teladoc.com",

    # === MISC BIG BRANDS ===
    "wikipedia.org", "wikimedia.org", "mediawiki.org",
    "mozilla.org", "mozilla.com", "firefox.com",
    "duckduckgo.com",
    "yelp.com",
    "craigslist.org",
    "zoom.us", "zoom.com",
    "dropbox.com",
    "tumblr.com",
    "wordpress.com",
    "squarespace.com",
    "wix.com",
    "weebly.com",
    "mailchimp.com",
    "constantcontact.com",
    "sendgrid.com",
    "twilio.com",
    "nexmo.com",
    "vonage.com",

    # === MORE TECH ===
    "hashicorp.com", "vaultproject.io",
    "terraform.io",
    "ansible.com",
    "puppet.com",
    "chef.io",
    "datadog.com",
    "splunk.com",
    "pagerduty.com",
    "opsgenie.com",
    "xenops.io",
    "grafana.com",
    "prometheus.io",
    "kubernetes.io",
    "docker.com",
    "rancher.com",
    "coreos.com",
    "redhat.com", "redhat.io",
    "suse.com",
    "centos.org",
    "ubuntu.com", "canonical.com",
    "debian.org",
    "linux.org",
    "gnu.org",
    "apache.org",
    "nginx.org",
    "redis.io",
    "postgresql.org",
    "mysql.com",
    "sqlite.org",
    "mongodb.com",
    "couchdb.org",
    "cassandra.apache.org",
    "neo4j.com",
    "arangodb.com",
    "influxdata.com",
    "timescale.com",
    "confluent.io",
    "pulsar.apache.org",
    "rabbitmq.com",
    "celeryproject.org",
    "socket.io",
    "graphql.org",
    "hasura.io",
    "prisma.io",
    "strapi.io",
    "contentful.com",
    "sanity.io",
    "storyblok.com",

    # === MORE BRANDS ===
    "ikea.com",
    "lego.com",
    "nike.com", "nike.com",
    "adidas.com",
    "puma.com",
    "zara.com",
    "hm.com",
    "uniqlo.com",
    "gucci.com",
    "lvmh.com",
    "rolex.com",
    "toyota.com",
    "honda.com",
    "ford.com",
    "gm.com",
    "tesla.com",
    "bmw.com",
    "mercedes-benz.com",
    "audi.com",
    "volkswagen.com",
    "hyundai.com",
    "kia.com",
    "nasa.gov",
    "who.int",
    "un.org",
    "worldbank.org",
    "imf.org",
    "oecd.org",
    "europa.eu",
    "gov.uk",
    "usa.gov",
    "irs.gov",
    "cdc.gov",
    "nih.gov",
    "fda.gov",
    "sec.gov",
    "fcc.gov",
}

# Domains that look like they could be expired but are actually parked/owned
PARKED_PATTERNS = re.compile(
    r"(buy|sell|cheap|discount|offer|deal|price|cost|pay|shop|store|market|auction|bid|bidder)"
    r".*\.(com|io|net|org)$",
    re.IGNORECASE,
)


class FreeDomainScraper:
    """Scrapes expired domains from free sources using simple HTTP requests."""

    def __init__(self) -> None:
        self.logger = setup_logger("FreeDomainScraper")

    async def fetch_all(self, max_domains: int = 300) -> list[dict]:
        """Fetch domains from all sources."""
        all_domains: list[str] = []

        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            # Source 1: ExpiredDomains.net (main source)
            try:
                domains = await self._scrape_expireddomains_net(client)
                all_domains.extend(domains)
                self.logger.info("expireddomains.net: %d domains", len(domains))
            except Exception as e:
                self.logger.warning("expireddomains.net failed: %s", e)

            # Source 2: Flippa (actual listings)
            try:
                domains = await self._scrape_flippa(client)
                all_domains.extend(domains)
                self.logger.info("flippa: %d domains", len(domains))
            except Exception as e:
                self.logger.warning("flippa failed: %s", e)

        # Deduplicate
        unique = list(dict.fromkeys(all_domains))
        self.logger.info("Total unique domains: %d", len(unique))

        # Convert to dicts and filter
        domain_dicts = [self._make_dict(d) for d in unique[:max_domains]]
        return filter_domains(domain_dicts)

    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain is valid and not excluded."""
        if not DOMAIN_RE.match(domain):
            return False
        if domain in EXCLUDE_DOMAINS:
            return False
        # Check if it's a subdomain of an excluded domain
        parts = domain.split(".")
        for i in range(len(parts)):
            test = ".".join(parts[i:])
            if test in EXCLUDE_DOMAINS:
                return False
        return True

    async def _scrape_expireddomains_net(self, client: httpx.AsyncClient) -> list[str]:
        """Scrape expireddomains.net for expired domains — ONLY from actual listings."""
        domains: list[str] = []

        # Only the main expired domains page (not random other pages)
        url = "https://www.expireddomains.net/expired-domains/"

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return domains

            soup = BeautifulSoup(resp.text, "html.parser")

            # Strategy 1: Find the main domain listing table
            # expireddomains.net puts domains in table rows with specific classes
            for table in soup.find_all("table"):
                # Check if this looks like a domain listing table
                headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
                if not any("domain" in h for h in headers):
                    continue  # Skip tables that don't list domains

                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue  # Skip header rows

                    # The first cell usually contains the domain name
                    first_cell = cells[0]
                    text = first_cell.get_text(strip=True).lower()

                    # Also check links in the cell
                    link = first_cell.find("a")
                    if link:
                        link_text = link.get_text(strip=True).lower()
                        if self._is_valid_domain(link_text):
                            domains.append(link_text)

                    if self._is_valid_domain(text):
                        domains.append(text)

            # Strategy 2: Find domain links in listing sections
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                text = a.get_text(strip=True).lower()

                # Only match links that look like domain listings
                # e.g., /domain/expired/example.com or similar
                if "/domain/" in href or "/expired/" in href:
                    if self._is_valid_domain(text):
                        domains.append(text)

        except Exception:
            pass

        return list(dict.fromkeys(domains))

    async def _scrape_flippa(self, client: httpx.AsyncClient) -> list[str]:
        """Scrape Flippa domain listings — ONLY from actual listing cards."""
        domains: list[str] = []

        try:
            resp = await client.get("https://flippa.com/domains")
            if resp.status_code != 200:
                return domains

            soup = BeautifulSoup(resp.text, "html.parser")

            # Flippa puts listings in specific card elements
            # Look for listing titles/links
            for card in soup.find_all(["div", "a"], class_=re.compile(r"listing|card|auction", re.I)):
                # Find domain name in the card
                title_el = card.find(["h2", "h3", "h4", "a"], class_=re.compile(r"title|name|heading", re.I))
                if title_el:
                    text = title_el.get_text(strip=True).lower()
                    if self._is_valid_domain(text):
                        domains.append(text)

            # Also check data attributes
            for el in soup.find_all(attrs={"data-domain": True}):
                domain = el.get("data-domain", "").lower()
                if self._is_valid_domain(domain):
                    domains.append(domain)

        except Exception:
            pass

        return list(dict.fromkeys(domains))

    def _make_dict(self, domain_name: str) -> dict:
        tld = domain_name.split(".")[-1]
        return {
            "domain_name": domain_name,
            "price": 0.0,
            "source": "free_scraper",
            "tld": tld,
            "dr": 0,
            "referring_domains": 0,
            "domain_age": 0,
        }
