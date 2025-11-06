import feedparser, httpx, json, re
from bs4 import BeautifulSoup
from typing import List, Dict, Iterable

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
}

async def fetch_rss(url: str) -> List[Dict]:
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:50]:
        items.append({
            "title": getattr(e, "title", ""),
            "url": getattr(e, "link", ""),
            "summary": getattr(e, "summary", ""),
            "published_at": getattr(e, "published_parsed", None),
        })
    return items

def _extract_json_array(text: str, required_keys: Iterable[str]) -> List[dict]:
    required_keys = set([k for k in required_keys if k])
    idx = 0
    while True:
        idx = text.find("[{", idx)
        if idx == -1:
            break
        depth = 0
        in_string = False
        escape = False
        for pos in range(idx, len(text)):
            ch = text[pos]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    in_string = False
            else:
                if ch == "\"":
                    in_string = True
                elif ch in "[{":
                    depth += 1
                elif ch in "]}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[idx:pos + 1]
                        try:
                            data = json.loads(candidate)
                        except json.JSONDecodeError:
                            break
                        if isinstance(data, list):
                            if not required_keys:
                                return data
                            for entry in data:
                                if isinstance(entry, dict) and required_keys.issubset(entry.keys()):
                                    return data
                        break
        idx += 2
    return []

async def fetch_html_list(url: str, rules: dict) -> List[Dict]:
    async with httpx.AsyncClient(timeout=20, headers=HEADERS, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    base_url = r.url
    items = []
    for node in soup.select(rules.get("item_selector", ""))[:50]:
        title_node = node.select_one(rules.get("title_selector", ""))
        if not title_node and rules.get("title_selector", "").strip() == node.name:
            title_node = node
        link_node = node.select_one(rules.get("title_selector", "")) or node.select_one("a")
        if not link_node and rules.get("title_selector", "").strip() == node.name:
            link_node = node
        summary_node = node.select_one(rules.get("summary_selector", ""))
        title = title_node.get_text(strip=True) if title_node else ""

        href = ""
        url_selector = rules.get("url_selector")
        if url_selector:
            attr_match = re.match(r"(.+?)::attr\(([^)]+)\)", url_selector)
            selector = url_selector
            attr_name = "href"
            if attr_match:
                selector = attr_match.group(1).strip()
                attr_name = attr_match.group(2).strip()
            target = node.select_one(selector) if selector else None
            if not target and selector and selector.strip() == node.name:
                target = node
            if target:
                href = target.get(attr_name, "")
        if not href and link_node:
            href = link_node.get("href", "")
        if href:
            href = str(base_url.join(href))
        summary = summary_node.get_text(strip=True) if summary_node else ""
        location = ""
        location_selector = rules.get("location_selector")
        if location_selector:
            loc_node = node.select_one(location_selector)
            if not loc_node and location_selector.strip() == node.name:
                loc_node = node
            if loc_node:
                location = loc_node.get_text(strip=True)
        if location and not summary:
            summary = location
        filters = rules.get("filters") or []
        include = True
        if filters:
            field_values = {
                "title": title,
                "summary": summary,
                "location": location,
            }
            for flt in filters:
                field = (flt or {}).get("field")
                contains = (flt or {}).get("contains")
                if field and contains:
                    field_val = field_values.get(field, "")
                    if contains.lower() not in field_val.lower():
                        include = False
                        break
        if not include:
            continue
        if title and href:
            items.append({"title": title, "url": href, "summary": summary, "location": location})
    if items:
        return items

    json_title = rules.get("json_title_key")
    json_url = rules.get("json_url_key")
    if json_title and json_url:
        json_entries = _extract_json_array(r.text, [json_title, json_url])
        if json_entries:
            out = []
            json_summary = rules.get("json_summary_key")
            filter_key = rules.get("json_filter_key")
            filter_value = rules.get("json_filter_value", "")
            filter_value_lower = filter_value.lower() if filter_value else ""
            for entry in json_entries:
                if not isinstance(entry, dict):
                    continue
                location = ""
                if filter_key and filter_value_lower:
                    field_val = str(entry.get(filter_key, "") or "")
                    if filter_value_lower not in field_val.lower():
                        continue
                    location = field_val
                elif filter_key:
                    location = str(entry.get(filter_key, "") or "")
                title = str(entry.get(json_title, "") or "").strip()
                href = str(entry.get(json_url, "") or "").strip()
                if not title or not href:
                    continue
                if href.startswith("//"):
                    href = f"{base_url.scheme}:{href}"
                href = str(base_url.join(href))
                summary_val = entry.get(json_summary, "") if json_summary else ""
                summary = ""
                if summary_val:
                    summary = BeautifulSoup(str(summary_val), "html.parser").get_text(" ", strip=True)
                if location and summary:
                    if location.lower() not in summary.lower():
                        summary = f"{summary} — {location}"
                elif location:
                    summary = location
                out.append({"title": title, "url": href, "summary": summary, "location": location})
                if len(out) >= 50:
                    break
            if out:
                return out
    return []
