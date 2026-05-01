import hashlib
import re
from urllib.parse import urlparse


DEFAULT_EMBODIED_CATEGORIES = "cs.RO, cs.AI, cs.LG, cs.CV, cs.CL, eess.SY"

DEFAULT_EMBODIED_KEYWORDS = (
    "embodied, embodied ai, embodied intelligence, robotics, robot, robot learning, "
    "robotic manipulation, manipulation, mobile manipulation, dexterous, dexterity, "
    "locomotion, navigation, mobile robot, humanoid, quadruped, legged robot, "
    "vision-language-action, vision language action, vla, vlm, multimodal, "
    "language-conditioned, language conditioned, instruction following, imitation learning, "
    "behavior cloning, reinforcement learning, policy learning, diffusion policy, visuomotor, "
    "sim-to-real, sim2real, real-to-sim, world model, foundation model, robot foundation model, "
    "affordance, tactile, grasping, pick and place, task and motion planning, tamp, "
    "motion planning, path planning, contact-rich, contact rich, teleoperation, bimanual"
)

DEFAULT_ROBOTICS_RSS_URLS = "\n".join(
    [
        "RSS|https://dblp.org/feed/streams/conf/rss.rss",
        "CoRL|https://dblp.org/feed/streams/conf/corl.rss",
        "ICRA|https://dblp.org/feed/streams/conf/icra.rss",
        "IROS|https://dblp.org/feed/streams/conf/iros.rss",
        "RA-L|https://dblp.org/feed/streams/journals/ral.rss",
        "T-RO|https://dblp.org/feed/streams/journals/trob.rss",
        "IJRR|https://dblp.org/feed/streams/journals/ijrr.rss",
        "Science Robotics|https://dblp.org/feed/streams/journals/scirobotics.rss",
        "Autonomous Robots|https://dblp.org/feed/streams/journals/arobots.rss",
        "Robotics and Autonomous Systems|https://dblp.org/feed/streams/journals/ras.rss",
    ]
)


def parse_list(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_rss_sources(value: str) -> list[dict[str, str]]:
    if value is None:
        value = DEFAULT_ROBOTICS_RSS_URLS

    sources = []
    entries = re.split(r"[\n;]+", value)
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        if "|" in entry:
            venue, url = [part.strip() for part in entry.split("|", 1)]
        else:
            url = entry
            parsed = urlparse(url)
            venue = parsed.path.strip("/").split("/")[-1] or parsed.netloc

        if url:
            sources.append({"venue": venue or "Robotics", "url": url})
    return sources


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    if not text or not keywords:
        return []

    text = text.lower()
    matches = []
    for keyword in keywords:
        normalized = keyword.strip().lower()
        if not normalized:
            continue

        if _matches_keyword(text, normalized):
            matches.append(keyword.strip())
    return matches


def stable_item_id(source: str, venue: str, url: str, title: str) -> str:
    base = url or title
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
    source = _slug(source or "paper")
    venue = _slug(venue or "unknown")
    return f"{source}:{venue}:{digest}"


def _matches_keyword(text: str, keyword: str) -> bool:
    if len(keyword) <= 4 and keyword.replace("-", "").replace("_", "").isalnum():
        pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
        return re.search(pattern, text) is not None
    return keyword in text


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "unknown"
