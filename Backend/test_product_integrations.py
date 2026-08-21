import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from live_search.integrations.router import ProductIntegrationRouter


DEMO_CASES = {
    "dishwasher": {
        "product_name": "Built-In Front Loading Dishwashing Machine",
        "keywords": [
            "built in dishwasher",
            "front loading dishwasher",
            "dishwasher detergent dispenser",
            "dishwasher rack guides",
        ],
        "reference_claims": [
            "A dishwashing machine having a washing chamber, racks, guides, a door, and detergent dispensing components.",
            "The appliance includes washing fluid distribution and an inner door arrangement configured for dishwashing operation.",
        ],
    },
    "vacuum": {
        "product_name": "Bagless Upright Vacuum Cleaner",
        "keywords": [
            "bagless vacuum cleaner",
            "upright vacuum cleaner",
            "cyclonic vacuum",
            "dust bin vacuum",
        ],
        "reference_claims": [
            "A vacuum cleaner comprising a suction motor, dust compartment, air guide, and filtration assembly.",
            "The cleaner includes a removable dust cup and airflow path for separating dirt from an air stream.",
        ],
    },
}


def main():
    parser = argparse.ArgumentParser(description="Smoke test product scraping integrations.")
    parser.add_argument("--case", choices=sorted(DEMO_CASES), default="dishwasher")
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument(
        "--offline-fixture",
        action="store_true",
        help="Use local HTML fixtures instead of live marketplace requests.",
    )
    args = parser.parse_args()

    case = DEMO_CASES[args.case]
    router = ProductIntegrationRouter(client=OfflineFixtureClient() if args.offline_fixture else None)
    products = router.search(
        product_name=case["product_name"],
        keywords=case["keywords"],
        reference_claims=case["reference_claims"],
        owners=[],
        search_limitations={
            "urls": [
                "https://www.amazon.com",
                "https://www.walmart.com",
                "https://www.ebay.com",
                "https://www.bestbuy.com",
                "https://www.samsung.com",
                "https://www.lg.com",
            ],
        },
        max_results=args.max_results,
    )
    print(json.dumps([product.model_dump() for product in products], indent=2))

class OfflineFixtureClient:
    def fetch_text(self, url: str, source: str = "product") -> str | None:
        del source
        lower = url.lower()
        if "amazon.com/s?" in lower:
            return """
            <html><body>
              <a href="/dp/B0DISHWASH1">Dishwasher product</a>
            </body></html>
            """
        if "/dp/b0dishwash1" in lower:
            return product_html(
                "Amazon Smart Built-In Dishwasher",
                "Built-in dishwasher with adjustable racks, detergent dispenser, stainless tub, and quiet wash cycle.",
            )
        if "walmart.com/search" in lower:
            return """
            <html><body>
              <a href="/ip/Quiet-Built-In-Dishwasher/123456789">Walmart dishwasher</a>
            </body></html>
            """
        if "walmart.com/ip/" in lower:
            return product_html(
                "Walmart Quiet Built-In Dishwasher",
                "Front control dishwasher with wash chamber, rack guides, spray arms, and heated drying.",
            )
        if "ebay.com/sch" in lower:
            return """
            <html><body>
              <a href="https://www.ebay.com/itm/335123456789">eBay dishwasher</a>
            </body></html>
            """
        if "ebay.com/itm/" in lower:
            return product_html(
                "eBay Built-In Dishwasher Replacement",
                "Dishwasher appliance with door seal, basket rack, pump, and detergent cup.",
            )
        if "bestbuy.com/site/search" in lower:
            return """
            <html><body>
              <a href="/site/lg-front-control-dishwasher/6543210.p">Best Buy dishwasher</a>
            </body></html>
            """
        if "bestbuy.com/site/" in lower:
            return product_html(
                "Best Buy LG Front Control Dishwasher",
                "Front-control dishwasher with adjustable upper rack, stainless steel tub, and multiple wash cycles.",
            )
        return None


def product_html(title: str, description: str) -> str:
    return f"""
    <html>
      <head>
        <title>{title}</title>
        <meta property="og:title" content="{title}" />
        <meta property="og:description" content="{description}" />
        <script type="application/ld+json">{{
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "{title}",
          "description": "{description}",
          "sku": "fixture-sku"
        }}</script>
      </head>
      <body>
        <h1>{title}</h1>
        <ul class="features">
          <li>{description}</li>
          <li>Includes appliance door, rack guide system, detergent dispenser, and wash chamber.</li>
        </ul>
      </body>
    </html>
    """


if __name__ == "__main__":
    main()
