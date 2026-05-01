import os

import arxiv
from scrapy.exceptions import DropItem

from daily_arxiv.curation import DEFAULT_EMBODIED_KEYWORDS, match_keywords, parse_list


class DailyArxivPipeline:
    def __init__(self):
        self.page_size = 100
        self.client = arxiv.Client(self.page_size)
        self.keywords = parse_list(os.environ.get("KEYWORDS") or DEFAULT_EMBODIED_KEYWORDS)
        self.keyword_filter_enabled = os.environ.get("KEYWORD_FILTER_ENABLED", "true").lower() not in {
            "0",
            "false",
            "no",
        }
        self.core_categories = set(parse_list(os.environ.get("CORE_CATEGORIES") or "cs.RO"))
        self.rss_require_keywords = os.environ.get("ROBOTICS_RSS_REQUIRE_KEYWORDS", "true").lower() not in {
            "0",
            "false",
            "no",
        }

    def process_item(self, item: dict, spider):
        source = item.get("source", "arxiv")

        if source == "arxiv":
            item = self._enrich_arxiv_item(item)
        else:
            item = self._normalize_external_item(item)

        matched_keywords = self._matched_keywords(item)
        item["matched_keywords"] = matched_keywords

        if self._should_keep(item, matched_keywords):
            return item

        raise DropItem(f"Filtered non-embodied paper: {item.get('title') or item.get('id')}")

    def _enrich_arxiv_item(self, item: dict) -> dict:
        item["source"] = "arxiv"
        item["venue"] = "arXiv"
        item["pdf"] = f"https://arxiv.org/pdf/{item['id']}"
        item["abs"] = f"https://arxiv.org/abs/{item['id']}"

        search = arxiv.Search(id_list=[item["id"]])
        paper = next(self.client.results(search))
        item["authors"] = [author.name for author in paper.authors]
        item["title"] = paper.title
        item["categories"] = self._primary_first(paper.categories, getattr(paper, "primary_category", None))
        item["comment"] = paper.comment
        item["summary"] = paper.summary
        return item

    @staticmethod
    def _normalize_external_item(item: dict) -> dict:
        item["source"] = item.get("source") or "external"
        item["venue"] = item.get("venue") or item["source"]
        item["categories"] = item.get("categories") or [item["venue"]]
        item["authors"] = item.get("authors") or []
        item["title"] = item.get("title") or item.get("id", "")
        item["summary"] = item.get("summary") or item["title"]
        item["comment"] = item.get("comment") or ""
        item["abs"] = item.get("abs") or item.get("url", "")
        item["pdf"] = item.get("pdf") or ""
        return item

    @staticmethod
    def _primary_first(categories, primary_category):
        categories = list(categories or [])
        if primary_category and primary_category in categories:
            return [primary_category] + [category for category in categories if category != primary_category]
        return categories

    def _matched_keywords(self, item: dict) -> list[str]:
        text = " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("summary") or ""),
                str(item.get("comment") or ""),
                " ".join(item.get("categories") or []),
            ]
        )
        return match_keywords(text, self.keywords)

    def _should_keep(self, item: dict, matched_keywords: list[str]) -> bool:
        if not self.keyword_filter_enabled:
            return True

        categories = set(item.get("categories") or [])
        if item.get("source") == "arxiv" and categories.intersection(self.core_categories):
            return True

        if item.get("source") != "arxiv" and not self.rss_require_keywords:
            return True

        return bool(matched_keywords)
