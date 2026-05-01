import html
import os
import re
from xml.etree import ElementTree

import scrapy

from daily_arxiv.curation import (
    DEFAULT_EMBODIED_CATEGORIES,
    parse_rss_sources,
    stable_item_id,
)


class ArxivSpider(scrapy.Spider):
    name = "arxiv"
    allowed_domains = ["arxiv.org", "dblp.org"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = os.environ.get("CATEGORIES") or DEFAULT_EMBODIED_CATEGORIES
        self.target_categories = {cat.strip() for cat in categories.split(",") if cat.strip()}
        self.arxiv_start_urls = [
            f"https://arxiv.org/list/{cat}/new" for cat in sorted(self.target_categories)
        ]

        rss_enabled = os.environ.get("ENABLE_ROBOTICS_RSS", "true").lower() not in {
            "0",
            "false",
            "no",
        }
        self.rss_sources = parse_rss_sources(os.environ.get("ROBOTICS_RSS_URLS") or None) if rss_enabled else []

    def start_requests(self):
        for url in self.arxiv_start_urls:
            yield scrapy.Request(url, callback=self.parse_arxiv_list)

        for source in self.rss_sources:
            yield scrapy.Request(
                source["url"],
                callback=self.parse_rss_feed,
                meta={"venue": source["venue"]},
                dont_filter=True,
            )

    def parse_arxiv_list(self, response):
        anchors = []
        for li in response.css("div[id=dlpage] ul li"):
            href = li.css("a::attr(href)").get()
            if href and "item" in href:
                anchors.append(int(href.split("item")[-1]))

        for paper in response.css("dl dt"):
            paper_anchor = paper.css("a[name^='item']::attr(name)").get()
            if not paper_anchor:
                continue

            paper_id = int(paper_anchor.split("item")[-1])
            if anchors and paper_id >= anchors[-1]:
                continue

            abstract_link = paper.css("a[title='Abstract']::attr(href)").get()
            if not abstract_link:
                continue

            arxiv_id = abstract_link.split("/")[-1]
            paper_dd = paper.xpath("following-sibling::dd[1]")
            if not paper_dd:
                continue

            subjects_text = paper_dd.css(".list-subjects .primary-subject::text").get()
            if not subjects_text:
                subjects_text = paper_dd.css(".list-subjects::text").get()

            if subjects_text:
                categories_in_paper = re.findall(r"\(([^)]+)\)", subjects_text)
                paper_categories = set(categories_in_paper)
                if paper_categories.intersection(self.target_categories):
                    yield {
                        "id": arxiv_id,
                        "categories": list(paper_categories),
                        "source": "arxiv",
                        "venue": "arXiv",
                    }
                    self.logger.info(f"Found paper {arxiv_id} with categories {paper_categories}")
                else:
                    self.logger.debug(
                        f"Skipped paper {arxiv_id} with categories {paper_categories} "
                        f"(not in target {self.target_categories})"
                    )
            else:
                self.logger.warning(f"Could not extract categories for paper {arxiv_id}, including anyway")
                yield {
                    "id": arxiv_id,
                    "categories": [],
                    "source": "arxiv",
                    "venue": "arXiv",
                }

    def parse_rss_feed(self, response):
        venue = response.meta.get("venue", "Robotics")
        try:
            root = ElementTree.fromstring(response.body)
        except ElementTree.ParseError as exc:
            self.logger.warning(f"Could not parse RSS feed for {venue}: {exc}")
            return

        for entry in root.iter():
            if self._local_name(entry.tag) != "item":
                continue

            title = self._clean_text(self._child_text(entry, {"title"}))
            link = self._clean_text(self._child_text(entry, {"link"}))
            description = self._clean_text(self._child_text(entry, {"description"}))
            creator = self._clean_text(self._child_text(entry, {"creator"}))
            date = self._clean_text(self._child_text(entry, {"date", "pubDate"}))

            if not title:
                continue

            yield {
                "id": stable_item_id("dblp", venue, link, title),
                "title": title,
                "authors": [creator] if creator else [],
                "summary": description or title,
                "comment": "",
                "categories": [venue],
                "source": "dblp",
                "venue": venue,
                "abs": link,
                "pdf": "",
                "published": date,
            }

    @staticmethod
    def _clean_text(value):
        if not value:
            return ""
        value = html.unescape(value)
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    @classmethod
    def _child_text(cls, entry, names):
        for child in entry:
            if cls._local_name(child.tag) in names:
                return "".join(child.itertext())
        return ""

    @staticmethod
    def _local_name(tag):
        if "}" in tag:
            return tag.rsplit("}", 1)[-1]
        return tag
