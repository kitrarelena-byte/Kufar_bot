import re

from playwright.async_api import async_playwright


def extract_id(link):

    if not link:
        return None

    m = re.search(r"/(\d+)$", link)

    if m:
        return m.group(1)

    return link


def parse_price(text):

    if not text:
        return None

    nums = re.findall(r"\d+", text.replace(" ", ""))

    if not nums:
        return None

    try:
        return float(nums[0])
    except:
        return None


async def fetch_ads_avby(url):

    ads = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page()

        try:

            print(f"[AVBY] {url}")

            await page.goto(
                url,
                timeout=60000
            )

            await page.wait_for_timeout(
                3000
            )

            links = await page.query_selector_all(
                "a[href*='/car/']"
            )

            seen = set()

            for link_el in links:

                href = await link_el.get_attribute(
                    "href"
                )

                if not href:
                    continue

                if not href.startswith(
                    "https://"
                ):
                    href = (
                        "https://av.by"
                        + href
                    )

                item_id = extract_id(
                    href
                )

                if item_id in seen:
                    continue

                seen.add(item_id)

                text = (
                    await link_el.inner_text()
                ).strip()

                if not text:
                    continue

                ads.append({
                    "id": item_id,
                    "text": text,
                    "link": href,
                    "price": None
                })

            ads = ads[:20]

            print(
                f"[AVBY] collected: {len(ads)}"
            )

            return ads

        finally:

            await browser.close()