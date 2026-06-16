from __future__ import annotations

import re
from typing import Any

import httpx

from src.config import settings
from src.utils import setup_logger

LEADS_BY_NICHE: dict[str, list[str]] = {
    "ai": [
        "OpenAI", "Anthropic", "Cohere", "Hugging Face", "Stability AI",
        "Jasper AI", "Copy.ai", "Writer.com", "Runway ML", "Midjourney",
        "Scale AI", "DataRobot", "H2O.ai", "C3 AI", "Pathmind",
    ],
    "saas": [
        "Salesforce", "HubSpot", "Zendesk", "Slack", "Atlassian",
        "Notion", "Airtable", "Asana", "Monday.com", "ClickUp",
        "Freshworks", "Intercom", "DocuSign", "Box", "Dropbox",
    ],
    "finance": [
        "Stripe", "Square", "Plaid", "Robinhood", "Coinbase",
        "PayPal", "Revolut", "Wise", "Klarna", "Affirm",
        "Chime", "Betterment", "Wealthfront", "SoFi", "Nubank",
    ],
    "health": [
        "Teladoc", "Ro", "Hims", "Noom", "Calm",
        "Headspace", "MyFitnessPal", "Fitbit", "Whoop", "Oura",
        "One Medical", "Carbon Health", "Zymergen", "Illumina", "23andMe",
    ],
    "ecommerce": [
        "Shopify", "BigCommerce", "Wix", "Squarespace", "WooCommerce",
        "Magento", "Salesforce Commerce", "PrestaShop", "OpenCart", "Ecwid",
        "Etsy", "Amazon", "eBay", "Walmart", "Target",
    ],
    "education": [
        "Coursera", "Udemy", "edX", "Khan Academy", "Duolingo",
        "Chegg", "Quizlet", "Byju's", "MasterClass", "Skillshare",
        "Pluralsight", "DataCamp", "Brilliant", "Codecademy", "Knewton",
    ],
    "cybersecurity": [
        "CrowdStrike", "Palo Alto", "Fortinet", "Zscaler", "Cloudflare",
        "Okta", "SentinelOne", "Darktrace", "Snyk", "Rapid7",
        "Tenable", "Check Point", "McAfee", "Trend Micro", "Cisco Security",
    ],
    "realestate": [
        "Zillow", "Redfin", "Compass", "Opendoor", "Realtor.com",
        "Airbnb", "Vrbo", "Booking.com", "CoStar", "Zumper",
        "Trulia", "Homes.com", "Reonomy", "CREXi", "LoopNet",
    ],
    "productivity": [
        "Notion", "Todoist", "Evernote", "Bear", "Roam Research",
        "Obsidian", "Miro", "Trello", "Notability", "GoodNotes",
        "Forest", "Focusmate", "RescueTime", "Clockify", "Toggl",
    ],
    "legal": [
        "LegalZoom", "Rocket Lawyer", "Avvo", "Clio", "MyCase",
        "PractiFi", "CaseText", "Casetext", "Ironclad", "Evisort",
        "LexisNexis", "Thomson Reuters", "DocuSign Legal", "LawGeex", "Definely",
    ],
}

MOCK_CONTACTS: dict[str, dict[str, str]] = {
    "OpenAI": {"contact_name": "Sam Altman", "contact_title": "CEO", "contact_email": "sam@openai.com", "contact_linkedin": "https://linkedin.com/in/samaltman"},
    "Anthropic": {"contact_name": "Dario Amodei", "contact_title": "CEO", "contact_email": "dario@anthropic.com", "contact_linkedin": "https://linkedin.com/in/dario-amodei"},
    "Anthropic PBC": {"contact_name": "Dario Amodei", "contact_title": "CEO", "contact_email": "dario@anthropic.com", "contact_linkedin": "https://linkedin.com/in/dario-amodei"},
    "Cohere": {"contact_name": "Aidan Gomez", "contact_title": "CEO", "contact_email": "aidan@cohere.com", "contact_linkedin": "https://linkedin.com/in/aidangomez"},
    "Hugging Face": {"contact_name": "Clement Delangue", "contact_title": "CEO", "contact_email": "clement@huggingface.co", "contact_linkedin": "https://linkedin.com/in/clementdelangue"},
    "Stability AI": {"contact_name": "Emad Mostaque", "contact_title": "CEO", "contact_email": "emad@stability.ai", "contact_linkedin": "https://linkedin.com/in/emadmostaque"},
    "Jasper AI": {"contact_name": "Dave Rogenmoser", "contact_title": "CEO", "contact_email": "dave@jasper.ai", "contact_linkedin": "https://linkedin.com/in/daverogenmoser"},
    "Copy.ai": {"contact_name": "Paul Yacoubian", "contact_title": "CEO", "contact_email": "paul@copy.ai", "contact_linkedin": "https://linkedin.com/in/paulyacoubian"},
    "Writer.com": {"contact_name": "May Habib", "contact_title": "CEO", "contact_email": "may@writer.com", "contact_linkedin": "https://linkedin.com/in/mayhabib"},
    "Runway ML": {"contact_name": "Cristobal Valenzuela", "contact_title": "CEO", "contact_email": "cristobal@runwayml.com", "contact_linkedin": "https://linkedin.com/in/cristobalvalenzuela"},
    "Midjourney": {"contact_name": "David Holz", "contact_title": "CEO", "contact_email": "david@midjourney.com", "contact_linkedin": "https://linkedin.com/in/davidholz"},
    "Scale AI": {"contact_name": "Alexandr Wang", "contact_title": "CEO", "contact_email": "alex@scale.com", "contact_linkedin": "https://linkedin.com/in/alexwang"},
    "DataRobot": {"contact_name": "Dan Wright", "contact_title": "CEO", "contact_email": "dan@datarobot.com", "contact_linkedin": "https://linkedin.com/in/danwright"},
    "H2O.ai": {"contact_name": "Sri Ambati", "contact_title": "CEO", "contact_email": "sri@h2o.ai", "contact_linkedin": "https://linkedin.com/in/sriambati"},
    "C3 AI": {"contact_name": "Thomas M. Siebel", "contact_title": "CEO", "contact_email": "tom@c3.ai", "contact_linkedin": "https://linkedin.com/in/tomsiebel"},
    "Pathmind": {"contact_name": "Chris Nicholson", "contact_title": "CEO", "contact_email": "chris@pathmind.com", "contact_linkedin": "https://linkedin.com/in/cwgreene"},
    "Salesforce": {"contact_name": "Marc Benioff", "contact_title": "CEO", "contact_email": "mbenioff@salesforce.com", "contact_linkedin": "https://linkedin.com/in/marcbenioff"},
    "HubSpot": {"contact_name": "Yamini Rangan", "contact_title": "CEO", "contact_email": "yamini@hubspot.com", "contact_linkedin": "https://linkedin.com/in/yamini-rangan"},
    "Zendesk": {"contact_name": "Mikkel Svane", "contact_title": "CEO", "contact_email": "mikkel@zendesk.com", "contact_linkedin": "https://linkedin.com/in/mikkelsvane"},
    "Slack": {"contact_name": "Lidiane Jones", "contact_title": "CEO", "contact_email": "lidiane@slack.com", "contact_linkedin": "https://linkedin.com/in/lidiane-jones"},
    "Atlassian": {"contact_name": "Mike Cannon-Brookes", "contact_title": "CEO", "contact_email": "mike@atlassian.com", "contact_linkedin": "https://linkedin.com/in/mike-cannon-brookes"},
    "Airtable": {"contact_name": "Howie Liu", "contact_title": "CEO", "contact_email": "howie@airtable.com", "contact_linkedin": "https://linkedin.com/in/howie-liu"},
    "Asana": {"contact_name": "Dustin Moskovitz", "contact_title": "CEO", "contact_email": "dustin@asana.com", "contact_linkedin": "https://linkedin.com/in/dustinmoskovitz"},
    "Monday.com": {"contact_name": "Roy Mann", "contact_title": "CEO", "contact_email": "roy@monday.com", "contact_linkedin": "https://linkedin.com/in/roymann"},
    "ClickUp": {"contact_name": "Zeb Evans", "contact_title": "CEO", "contact_email": "zeb@clickup.com", "contact_linkedin": "https://linkedin.com/in/zebevans"},
    "Freshworks": {"contact_name": "Girish Mathrubootham", "contact_title": "CEO", "contact_email": "girish@freshworks.com", "contact_linkedin": "https://linkedin.com/in/girishm"},
    "Intercom": {"contact_name": "Eoghan McCabe", "contact_title": "CEO", "contact_email": "eoghan@intercom.com", "contact_linkedin": "https://linkedin.com/in/eoghanmccabe"},
    "DocuSign": {"contact_name": "Allan Thygesen", "contact_title": "CEO", "contact_email": "allan@docusign.com", "contact_linkedin": "https://linkedin.com/in/allanthygesen"},
    "Box": {"contact_name": "Aaron Levie", "contact_title": "CEO", "contact_email": "aaron@box.com", "contact_linkedin": "https://linkedin.com/in/aaronlevie"},
    "Dropbox": {"contact_name": "Drew Houston", "contact_title": "CEO", "contact_email": "drew@dropbox.com", "contact_linkedin": "https://linkedin.com/in/drewhouston"},
    "Stripe": {"contact_name": "Patrick Collison", "contact_title": "CEO", "contact_email": "patrick@stripe.com", "contact_linkedin": "https://linkedin.com/in/patrickcollison"},
    "Square": {"contact_name": "Alyssa Henry", "contact_title": "CEO", "contact_email": "alyssa@square.com", "contact_linkedin": "https://linkedin.com/in/alyssahenry"},
    "Plaid": {"contact_name": "Zach Perret", "contact_title": "CEO", "contact_email": "zach@plaid.com", "contact_linkedin": "https://linkedin.com/in/zachperret"},
    "Robinhood": {"contact_name": "Vlad Tenev", "contact_title": "CEO", "contact_email": "vlad@robinhood.com", "contact_linkedin": "https://linkedin.com/in/vladtenev"},
    "Coinbase": {"contact_name": "Brian Armstrong", "contact_title": "CEO", "contact_email": "brian@coinbase.com", "contact_linkedin": "https://linkedin.com/in/brianarmstrong"},
    "PayPal": {"contact_name": "Alex Chriss", "contact_title": "CEO", "contact_email": "achriss@paypal.com", "contact_linkedin": "https://linkedin.com/in/alexchriss"},
    "Revolut": {"contact_name": "Nikolay Storonsky", "contact_title": "CEO", "contact_email": "nikolay@revolut.com", "contact_linkedin": "https://linkedin.com/in/nikolaystoronsky"},
    "Wise": {"contact_name": "Kristo Käärmann", "contact_title": "CEO", "contact_email": "kristo@wise.com", "contact_linkedin": "https://linkedin.com/in/kristokaarmann"},
    "Klarna": {"contact_name": "Sebastian Siemiatkowski", "contact_title": "CEO", "contact_email": "sebastian@klarna.com", "contact_linkedin": "https://linkedin.com/in/sebastiansiemiatkowski"},
    "Affirm": {"contact_name": "Max Levchin", "contact_title": "CEO", "contact_email": "max@affirm.com", "contact_linkedin": "https://linkedin.com/in/maxlevchin"},
    "Chime": {"contact_name": "Chris Britt", "contact_title": "CEO", "contact_email": "chris@chime.com", "contact_linkedin": "https://linkedin.com/in/chrisbritt"},
    "Betterment": {"contact_name": "Jon Stein", "contact_title": "CEO", "contact_email": "jon@betterment.com", "contact_linkedin": "https://linkedin.com/in/jonstein"},
    "Wealthfront": {"contact_name": "Andy Rachleff", "contact_title": "CEO", "contact_email": "andy@wealthfront.com", "contact_linkedin": "https://linkedin.com/in/andyrachleff"},
    "SoFi": {"contact_name": "Anthony Noto", "contact_title": "CEO", "contact_email": "anthony@sofi.com", "contact_linkedin": "https://linkedin.com/in/anthonymnoto"},
    "Nubank": {"contact_name": "David Velez", "contact_title": "CEO", "contact_email": "david@nubank.com.br", "contact_linkedin": "https://linkedin.com/in/davidvelez"},
    "Teladoc": {"contact_name": "Jason Gorevic", "contact_title": "CEO", "contact_email": "jason@teladoc.com", "contact_linkedin": "https://linkedin.com/in/jasongorevic"},
    "Ro": {"contact_name": "Zachariah Reitano", "contact_title": "CEO", "contact_email": "zach@ro.co", "contact_linkedin": "https://linkedin.com/in/zachreitano"},
    "Hims": {"contact_name": "Andrew Dudum", "contact_title": "CEO", "contact_email": "andrew@hims.com", "contact_linkedin": "https://linkedin.com/in/andrewdudum"},
    "Noom": {"contact_name": "Geoffrey Cook", "contact_title": "CEO", "contact_email": "geoff@noom.com", "contact_linkedin": "https://linkedin.com/in/geoffreycook"},
    "Calm": {"contact_name": "Alex Tew", "contact_title": "CEO", "contact_email": "alex@calm.com", "contact_linkedin": "https://linkedin.com/in/alextew"},
    "Headspace": {"contact_name": "CeCe Morken", "contact_title": "CEO", "contact_email": "cece@headspace.com", "contact_linkedin": "https://linkedin.com/in/cecemorken"},
    "MyFitnessPal": {"contact_name": "Mike Cadogan", "contact_title": "CEO", "contact_email": "mike@myfitnesspal.com", "contact_linkedin": "https://linkedin.com/in/mikecadogan"},
    "Fitbit": {"contact_name": "James Park", "contact_title": "CEO", "contact_email": "james@fitbit.com", "contact_linkedin": "https://linkedin.com/in/jamespark"},
    "Whoop": {"contact_name": "Will Ahmed", "contact_title": "CEO", "contact_email": "will@whoop.com", "contact_linkedin": "https://linkedin.com/in/willahmed"},
    "Oura": {"contact_name": "Tom Hale", "contact_title": "CEO", "contact_email": "tom@ouraring.com", "contact_linkedin": "https://linkedin.com/in/tomhale"},
    "One Medical": {"contact_name": "Amir Dan Rubin", "contact_title": "CEO", "contact_email": "amir@onemedical.com", "contact_linkedin": "https://linkedin.com/in/amirdanrubin"},
    "Carbon Health": {"contact_name": "Eren Bali", "contact_title": "CEO", "contact_email": "eren@carbonhealth.com", "contact_linkedin": "https://linkedin.com/in/erenbali"},
    "Zymergen": {"contact_name": "Jay Kou", "contact_title": "CEO", "contact_email": "jay@zymergen.com", "contact_linkedin": "https://linkedin.com/in/jaykou"},
    "Illumina": {"contact_name": "Jacob Thaysen", "contact_title": "CEO", "contact_email": "jthaysen@illumina.com", "contact_linkedin": "https://linkedin.com/in/jacobthaysen"},
    "23andMe": {"contact_name": "Anne Wojcicki", "contact_title": "CEO", "contact_email": "anne@23andme.com", "contact_linkedin": "https://linkedin.com/in/annewojcicki"},
    "Shopify": {"contact_name": "Tobi Lütke", "contact_title": "CEO", "contact_email": "tobi@shopify.com", "contact_linkedin": "https://linkedin.com/in/tobiaslutke"},
    "BigCommerce": {"contact_name": "Brent Bellm", "contact_title": "CEO", "contact_email": "brent@bigcommerce.com", "contact_linkedin": "https://linkedin.com/in/brentbellm"},
    "Wix": {"contact_name": "Avishai Abrahami", "contact_title": "CEO", "contact_email": "avishai@wix.com", "contact_linkedin": "https://linkedin.com/in/avishaiabrahami"},
    "Squarespace": {"contact_name": "Anthony Casalena", "contact_title": "CEO", "contact_email": "anthony@squarespace.com", "contact_linkedin": "https://linkedin.com/in/anthonycasalena"},
    "Etsy": {"contact_name": "Josh Silverman", "contact_title": "CEO", "contact_email": "josh@etsy.com", "contact_linkedin": "https://linkedin.com/in/joshsilverman"},
    "Amazon": {"contact_name": "Andy Jassy", "contact_title": "CEO", "contact_email": "ajassy@amazon.com", "contact_linkedin": "https://linkedin.com/in/andyjassy"},
    "Walmart": {"contact_name": "Doug McMillon", "contact_title": "CEO", "contact_email": "doug@walmart.com", "contact_linkedin": "https://linkedin.com/in/dougmcmillon"},
    "Target": {"contact_name": "Brian Cornell", "contact_title": "CEO", "contact_email": "brian@target.com", "contact_linkedin": "https://linkedin.com/in/briancornell"},
    "Coursera": {"contact_name": "Jeff Maggioncalda", "contact_title": "CEO", "contact_email": "jeff@coursera.org", "contact_linkedin": "https://linkedin.com/in/jeffmaggioncalda"},
    "Udemy": {"contact_name": "Gregg Coccari", "contact_title": "CEO", "contact_email": "gregg@udemy.com", "contact_linkedin": "https://linkedin.com/in/greggcoccari"},
    "edX": {"contact_name": "Anant Agarwal", "contact_title": "CEO", "contact_email": "anant@edx.org", "contact_linkedin": "https://linkedin.com/in/anantagarwal"},
    "Khan Academy": {"contact_name": "Sal Khan", "contact_title": "CEO", "contact_email": "sal@khanacademy.org", "contact_linkedin": "https://linkedin.com/in/salkhan"},
    "Duolingo": {"contact_name": "Luis von Ahn", "contact_title": "CEO", "contact_email": "luis@duolingo.com", "contact_linkedin": "https://linkedin.com/in/luisvonahn"},
    "Chegg": {"contact_name": "Dan Rosensweig", "contact_title": "CEO", "contact_email": "dan@chegg.com", "contact_linkedin": "https://linkedin.com/in/danrosensweig"},
    "Quizlet": {"contact_name": "Lex Bayer", "contact_title": "CEO", "contact_email": "lex@quizlet.com", "contact_linkedin": "https://linkedin.com/in/lexbayer"},
    "MasterClass": {"contact_name": "David Rogier", "contact_title": "CEO", "contact_email": "david@masterclass.com", "contact_linkedin": "https://linkedin.com/in/davidrogier"},
    "Skillshare": {"contact_name": "Matt Lieber", "contact_title": "CEO", "contact_email": "matt@skillshare.com", "contact_linkedin": "https://linkedin.com/in/mattlieber"},
    "Pluralsight": {"contact_name": "Aaron Skonnard", "contact_title": "CEO", "contact_email": "aaron@pluralsight.com", "contact_linkedin": "https://linkedin.com/in/aaronskonnard"},
    "DataCamp": {"contact_name": "Martijn Theuwissen", "contact_title": "CEO", "contact_email": "martijn@datacamp.com", "contact_linkedin": "https://linkedin.com/in/martijntheuwissen"},
    "Brilliant": {"contact_name": "Sue Khim", "contact_title": "CEO", "contact_email": "sue@brilliant.org", "contact_linkedin": "https://linkedin.com/in/suekhim"},
    "Codecademy": {"contact_name": "Zach Sims", "contact_title": "CEO", "contact_email": "zach@codecademy.com", "contact_linkedin": "https://linkedin.com/in/zachsims"},
    "CrowdStrike": {"contact_name": "George Kurtz", "contact_title": "CEO", "contact_email": "george@crowdstrike.com", "contact_linkedin": "https://linkedin.com/in/georgekurtz"},
    "Palo Alto Networks": {"contact_name": "Nikesh Arora", "contact_title": "CEO", "contact_email": "nikesh@paloaltonetworks.com", "contact_linkedin": "https://linkedin.com/in/nikesharora"},
    "Fortinet": {"contact_name": "Ken Xie", "contact_title": "CEO", "contact_email": "ken@fortinet.com", "contact_linkedin": "https://linkedin.com/in/kenxie"},
    "Zscaler": {"contact_name": "Jay Chaudhry", "contact_title": "CEO", "contact_email": "jay@zscaler.com", "contact_linkedin": "https://linkedin.com/in/jaychaudhry"},
    "Cloudflare": {"contact_name": "Matthew Prince", "contact_title": "CEO", "contact_email": "matthew@cloudflare.com", "contact_linkedin": "https://linkedin.com/in/matthewprince"},
    "Okta": {"contact_name": "Todd McKinnon", "contact_title": "CEO", "contact_email": "todd@okta.com", "contact_linkedin": "https://linkedin.com/in/toddmckinnon"},
    "SentinelOne": {"contact_name": "Tomer Weingarten", "contact_title": "CEO", "contact_email": "tomer@sentinelone.com", "contact_linkedin": "https://linkedin.com/in/tomerweingarten"},
    "Darktrace": {"contact_name": "Poppy Gustafsson", "contact_title": "CEO", "contact_email": "poppy@darktrace.com", "contact_linkedin": "https://linkedin.com/in/poppygustafsson"},
    "Snyk": {"contact_name": "Peter McKay", "contact_title": "CEO", "contact_email": "peter@snyk.io", "contact_linkedin": "https://linkedin.com/in/petermckay"},
    "Rapid7": {"contact_name": "Corey Thomas", "contact_title": "CEO", "contact_email": "corey@rapid7.com", "contact_linkedin": "https://linkedin.com/in/coreyrthomas"},
    "Tenable": {"contact_name": "Amit Yoran", "contact_title": "CEO", "contact_email": "amit@tenable.com", "contact_linkedin": "https://linkedin.com/in/amityoran"},
    "Zillow": {"contact_name": "Rich Barton", "contact_title": "CEO", "contact_email": "rich@zillow.com", "contact_linkedin": "https://linkedin.com/in/richbarton"},
    "Redfin": {"contact_name": "Glenn Kelman", "contact_title": "CEO", "contact_email": "glenn@redfin.com", "contact_linkedin": "https://linkedin.com/in/glennkelman"},
    "Compass": {"contact_name": "Robert Reffkin", "contact_title": "CEO", "contact_email": "robert@compass.com", "contact_linkedin": "https://linkedin.com/in/robertreffkin"},
    "Opendoor": {"contact_name": "Eric Wu", "contact_title": "CEO", "contact_email": "eric@opendoor.com", "contact_linkedin": "https://linkedin.com/in/ericwu"},
    "Airbnb": {"contact_name": "Brian Chesky", "contact_title": "CEO", "contact_email": "brian@airbnb.com", "contact_linkedin": "https://linkedin.com/in/brianchesky"},
    "Booking.com": {"contact_name": "Glenn Fogel", "contact_title": "CEO", "contact_email": "glenn@booking.com", "contact_linkedin": "https://linkedin.com/in/glennfogel"},
    "CoStar": {"contact_name": "Andy Florance", "contact_title": "CEO", "contact_email": "andy@costar.com", "contact_linkedin": "https://linkedin.com/in/andyflorance"},
    "Zumper": {"contact_name": "Anthemos Georgiades", "contact_title": "CEO", "contact_email": "anthemos@zumper.com", "contact_linkedin": "https://linkedin.com/in/anthemosg"},
    "Todoist": {"contact_name": "Amir Salihefendic", "contact_title": "CEO", "contact_email": "amir@todoist.com", "contact_linkedin": "https://linkedin.com/in/amirefendi"},
    "Evernote": {"contact_name": "Luca Barbetti", "contact_title": "CEO", "contact_email": "luca@evernote.com", "contact_linkedin": "https://linkedin.com/in/lucabarbetti"},
    "Miro": {"contact_name": "Andrey Khusid", "contact_title": "CEO", "contact_email": "andrey@miro.com", "contact_linkedin": "https://linkedin.com/in/andreykhusid"},
    "Trello": {"contact_name": "Javier Soltero", "contact_title": "CEO", "contact_email": "javier@trello.com", "contact_linkedin": "https://linkedin.com/in/javiersoltero"},
    "LegalZoom": {"contact_name": "Dan Wernikoff", "contact_title": "CEO", "contact_email": "dan@legalzoom.com", "contact_linkedin": "https://linkedin.com/in/danwernikoff"},
    "Rocket Lawyer": {"contact_name": "Charley Moore", "contact_title": "CEO", "contact_email": "charley@rocketlawyer.com", "contact_linkedin": "https://linkedin.com/in/charleymoore"},
    "Clio": {"contact_name": "Jack Newton", "contact_title": "CEO", "contact_email": "jack@clio.com", "contact_linkedin": "https://linkedin.com/in/jacknewton"},
    "Ironclad": {"contact_name": "Jason Boehmig", "contact_title": "CEO", "contact_email": "jason@ironcladapp.com", "contact_linkedin": "https://linkedin.com/in/jasonboehmig"},
    "Evisort": {"contact_name": "Amine Anoun", "contact_title": "CEO", "contact_email": "amine@evisort.com", "contact_linkedin": "https://linkedin.com/in/amineanoun"},
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class BuyerEnricher:
    def __init__(self) -> None:
        self.logger = setup_logger("BuyerEnricher")

    async def enrich(self, leads: list[dict[str, Any]], domain: str, niche: str) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []

        for lead in leads:
            try:
                company = lead.get("company", "")
                result: dict[str, Any] = {
                    **lead,
                    "contact_name": None,
                    "contact_title": None,
                    "contact_email": None,
                    "contact_linkedin": None,
                    "confidence": "none",
                }

                if settings.offline_mode:
                    self._apply_mock_contact(company, result)
                else:
                    await self._search_contact(company, domain, result)

                if result["contact_name"] is None:
                    result.pop("confidence", None)
                    result["contact_name"] = lead.get("contact_name")
                    result["contact_title"] = lead.get("contact_title")
                    result["contact_email"] = lead.get("contact_email")
                    result["contact_linkedin"] = lead.get("contact_linkedin")
                    result["confidence"] = lead.get("confidence", "none")

                enriched.append(result)

            except Exception as exc:
                self.logger.warning("Failed to enrich lead %s: %s", lead.get("company"), exc)
                enriched.append({
                    **lead,
                    "contact_name": None,
                    "contact_title": None,
                    "contact_email": None,
                    "contact_linkedin": None,
                    "confidence": "error",
                })

        return enriched

    def _apply_mock_contact(self, company: str, result: dict[str, Any]) -> None:
        mock = MOCK_CONTACTS.get(company)
        if mock:
            result["contact_name"] = mock["contact_name"]
            result["contact_title"] = mock["contact_title"]
            result["contact_email"] = mock["contact_email"]
            result["contact_linkedin"] = mock["contact_linkedin"]
            result["confidence"] = "high"
        else:
            slug = company.lower().replace(" ", "").replace(",", "").replace(".", "")
            result["contact_name"] = f"{company} Team"
            result["contact_title"] = "Director"
            result["contact_email"] = f"hello@{slug}.com"
            result["contact_linkedin"] = f"https://linkedin.com/company/{slug}"
            result["confidence"] = "generated"

    async def _search_contact(self, company: str, domain: str, result: dict[str, Any]) -> None:
        slug = company.lower().replace(" ", "").replace(",", "").replace(".", "")
        company_domain = domain
        if "." in domain:
            _, tld = domain.rsplit(".", 1)
            company_domain = f"{slug}.{tld}"

        linkedin_found = await self._search_linkedin(company)
        email_found = await self._search_email(company, company_domain)

        if linkedin_found:
            result["contact_name"] = linkedin_found.get("name")
            result["contact_title"] = linkedin_found.get("title")
            result["contact_linkedin"] = linkedin_found.get("url")

        if email_found:
            result["contact_email"] = email_found

        if linkedin_found or email_found:
            result["confidence"] = "found"
        else:
            first_name = company.split()[0].lower() if company.split() else "hello"
            result["contact_name"] = f"{company} Team"
            result["contact_title"] = "Director"
            result["contact_email"] = f"{first_name}@{company_domain}" if company_domain else f"{first_name}@company.com"
            result["contact_linkedin"] = f"https://linkedin.com/company/{slug}"
            result["confidence"] = "generated"

    async def _search_linkedin(self, company: str) -> dict[str, str] | None:
        query = f"site:linkedin.com/in \"{company}\""
        search_url = f"https://www.google.com/search?q={self._urlencode(query)}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    self.logger.debug("LinkedIn search returned %d for %s", resp.status_code, company)
                    return None

                text = resp.text
                name = self._extract_name_from_snippet(text, company)
                title = self._extract_title_from_snippet(text)
                url = self._extract_linkedin_url(text)

                if name or url:
                    return {"name": name, "title": title, "url": url}
                return None

        except httpx.TimeoutException:
            self.logger.debug("LinkedIn search timeout for %s", company)
            return None
        except httpx.HTTPError as exc:
            self.logger.debug("LinkedIn search HTTP error for %s: %s", company, exc)
            return None
        except OSError as exc:
            self.logger.debug("LinkedIn search connection error for %s: %s", company, exc)
            return None

    async def _search_email(self, company: str, company_domain: str) -> str | None:
        query = f"\"@{company_domain}\""
        search_url = f"https://www.google.com/search?q={self._urlencode(query)}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    return None

                emails = re.findall(rf"[a-zA-Z0-9._%+-]+@{re.escape(company_domain)}", resp.text)
                if emails:
                    return emails[0]
                return None

        except httpx.TimeoutException:
            self.logger.debug("Email search timeout for %s", company)
            return None
        except httpx.HTTPError as exc:
            self.logger.debug("Email search HTTP error for %s: %s", company, exc)
            return None
        except OSError as exc:
            self.logger.debug("Email search connection error for %s: %s", company, exc)
            return None

    def _extract_name_from_snippet(self, html: str, company: str) -> str | None:
        match = re.search(rf'<h3[^>]*>([^<]*)</h3>', html, re.IGNORECASE)
        if match:
            text = match.group(1)
            text = re.sub(r'<[^>]+>', '', text)
            text = text.strip()
            if text and len(text) < 200:
                return text
        match = re.search(r'((?:<span[^>]*>)*?([A-Z][a-z]+ [A-Z][a-z]+)(?:</span>)*?)', html)
        if match:
            return match.group(2)
        return None

    def _extract_title_from_snippet(self, html: str) -> str | None:
        for role in ("CEO", "CTO", "CFO", "COO", "Founder", "Co-Founder", "President", "Director", "VP", "Head of", "Lead", "Manager"):
            pattern = re.escape(role)
            if re.search(pattern, html, re.IGNORECASE):
                match = re.search(r'([A-Za-z\s&/,-]{2,60}(?:CEO|CTO|CFO|COO|Founder|Co-Founder|President|Director|VP|Head\s+of|Lead|Manager))', html)
                if match:
                    return match.group(1).strip()
                return role
        return None

    def _extract_linkedin_url(self, html: str) -> str | None:
        match = re.search(r'(https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+)', html)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _urlencode(query: str) -> str:
        return query.replace(" ", "+").replace("\"", "%22")
