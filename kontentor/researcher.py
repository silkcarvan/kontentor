"""Wikipedia Researcher Agent for Central Asian History, Rulers, Scholars & Culture."""

import json
import urllib.parse
import urllib.request
from typing import Dict, List

CURATED_FALLBACK_ENCYCLOPEDIA: Dict[str, Dict[str, str]] = {
    "Battle of Talas": {
        "title": "Battle of Talas (751 AD) & Samarkand Paper",
        "summary": (
            "In July 751 AD, the Abbasid Caliphate and the Tang Dynasty clashed at the "
            "Battle of Talas River on the border of modern Kazakhstan and Kyrgyzstan. "
            "Before this battle, books in the West and Middle East were written on expensive "
            "parchment made from scraping dozens of sheep or goat hides. Following the battle, "
            "Chinese artisans skilled in papermaking were brought to Samarkand. Samarkand "
            "perfected paper manufacturing using mulberry bark, hemp, and linen, creating "
            "smooth, durable 'Samarkand paper' that fueled the Islamic Golden Age and "
            "transformed human civilization."
        ),
    },
    "Timur": {
        "title": "Amir Temur (Tamerlane) — The Undefeated Strategist of Samarkand",
        "summary": (
            "Timur (1336–1405), known in Central Asia as Amir Temur (Sahibqiron), rose from "
            "minor noble origins near Kesh (modern Shahrisabz, Uzbekistan) to found the Timurid "
            "Empire. Never defeated on the battlefield, he united Central Asia, Persia, and parts "
            "of India and Anatolia. He transformed his capital, Samarkand, into the dazzling pearl "
            "of the Silk Road by bringing the world's finest architects, astronomers, and artisans "
            "to build monumental masterpieces like the Bibi-Khanym Mosque and Gur-e-Amir, igniting "
            "the Timurid Renaissance."
        ),
    },
    "Al-Khwarizmi": {
        "title": "Muhammad ibn Musa al-Khwarizmi — Father of Algebra & Algorithms",
        "summary": (
            "Born around 780 AD in Khwarazm (modern Khiva/Urgench region of Uzbekistan), "
            "Muhammad ibn Musa al-Khwarizmi was a Central Asian polymath whose works changed "
            "mathematics forever. His book 'Al-Jabr' gave the world the word 'Algebra', and the "
            "Latin translation of his name ('Algoritmi') gave us the word 'Algorithm'. Every "
            "computer, smartphone, and AI system today runs on concepts pioneered by this genius "
            "from Khwarazm."
        ),
    },
    "Ulugh Beg": {
        "title": "Mirzo Ulugh Beg — The Astronomer King of Samarkand",
        "summary": (
            "Ulugh Beg (1394–1449), grandson of Amir Temur and ruler of Samarkand, preferred "
            "mapping the cosmos over waging war. In the 1420s, he built the monumental Ulugh Beg "
            "Observatory in Samarkand housing a giant 40-meter marble sextant. Nearly two centuries "
            "before Galileo's telescope, Ulugh Beg cataloged 1,018 stars and calculated the length "
            "of the sidereal year to within 58 seconds of modern satellite measurements."
        ),
    },
    "Avicenna": {
        "title": "Ibn Sina (Avicenna) — The Bukhara Polymath Who Healed the World",
        "summary": (
            "Born in 980 AD in Afshona near Bukhara (modern Uzbekistan), Ibn Sina mastered "
            "medicine by age 16 and cured the Samanid Emir, gaining access to the Royal Library "
            "of Bukhara. His monumental five-volume 'Canon of Medicine' introduced clinical trials, "
            "quarantine to stop infectious diseases, and systematic pharmacology, serving as the "
            "standard medical textbook across Europe and the Middle East for over 600 years."
        ),
    },
}


class WikipediaResearcher:
    """Fetches and structures historical research from Wikipedia API."""

    USER_AGENT = "KontentorHistoryAgent/1.0 (CentralAsianHistoryChannel; educational)"

    def search_and_fetch(self, query: str) -> Dict[str, str]:
        """Search Wikipedia for a Central Asian topic and return structured facts."""
        try:
            search_url = (
                "https://en.wikipedia.org/w/api.php?"
                + urllib.parse.urlencode(
                    {
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "format": "json",
                        "srlimit": 1,
                    }
                )
            )
            req = urllib.request.Request(
                search_url, headers={"User-Agent": self.USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                search_data = json.loads(resp.read().decode("utf-8"))

            hits = search_data.get("query", {}).get("search", [])
            page_title = hits[0]["title"] if hits else query

            summary_url = (
                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                + urllib.parse.quote(page_title.replace(" ", "_"))
            )
            req2 = urllib.request.Request(
                summary_url, headers={"User-Agent": self.USER_AGENT}
            )
            with urllib.request.urlopen(req2, timeout=8) as resp2:
                summary_data = json.loads(resp2.read().decode("utf-8"))

            return {
                "title": summary_data.get("title", page_title),
                "summary": summary_data.get("extract", ""),
                "url": summary_data.get("content_urls", {})
                .get("desktop", {})
                .get("page", ""),
                "source": "wikipedia_live",
            }
        except Exception:
            # Offline or sandbox fallback using built-in curated Central Asian encyclopedia
            for key, entry in CURATED_FALLBACK_ENCYCLOPEDIA.items():
                if key.lower() in query.lower() or query.lower() in entry["title"].lower():
                    return {
                        "title": entry["title"],
                        "summary": entry["summary"],
                        "url": f"https://en.wikipedia.org/wiki/{key.replace(' ', '_')}",
                        "source": "curated_encyclopedia_fallback",
                    }
            return {
                "title": query,
                "summary": (
                    f"Historical topic from Central Asia: {query}. Focus on the Silk Road, "
                    "rulers, scholars, architectural wonders of Samarkand, Bukhara, and Khiva, "
                    "and their lasting impact on global civilization."
                ),
                "url": "",
                "source": "fallback",
            }

    @staticmethod
    def list_recommended_topics() -> List[str]:
        """Return high-RPM English Central Asian history topics."""
        return [
            "Battle of Talas (751 AD) and the Secret of Samarkand Paper",
            "Amir Temur: How a Shepherd's Son Built the Timurid Empire",
            "Ulugh Beg: The Samarkand Sultan Who Mapped 1,018 Stars Without a Telescope",
            "Al-Khwarizmi: The Central Asian Genius Behind Every Computer Algorithm",
            "Ibn Sina (Avicenna): How a Teenager from Bukhara Invented Quarantine",
            "Queen Tomyris: The Nomadic Queen Who Defeated Cyrus the Great",
            "Al-Biruni: Measuring the Earth's Radius in Khwarazm 1,000 Years Ago",
            "Registan of Samarkand: Hidden Secrets of the Silk Road's Crown Jewel",
        ]
