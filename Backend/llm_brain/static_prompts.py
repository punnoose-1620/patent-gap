PATENT_METADATA_EXTRACTOR = """
You are an expert patent data extractor.
You will be given the full text of a patent record (including header and body).

Your task is to extract **all** available metadata and return a **single JSON object** that
matches the schema provided by the caller. You **must include every key in the schema**
in your JSON output.

For any field that is **not explicitly available** in the text, follow these rules:
- If the field is a **string**, return an empty string `""`.
- If the field is a **number**, return `0`.
- If the field is a **list**, return an empty list `[]`.
- Never omit keys, and never change key names.

The fields to extract are:
- `_id`: Unique identifier for the patent (use the best identifier you can find in the text; if multiple IDs exist, choose the main publication/application number; if nothing is clearly an ID, return `""`).
- `title`: Title of the patent.
- `status`: Current legal/status description of the patent.
- `description`: High-level description/abstract of the patent.
- `currentStatusCode`: Numeric code (if one is explicitly given in the text). If not present, return `0`.
- `currentStatusDate`: Date when the status was last updated (or the most recent legal status date).
- `filingDate`: Filing date of the patent.
- `documents`: List of `DocumentsData` objects for any clearly identified documents.
- `document_urls`: List of URLs for any documents (including PDF/HTML links).
- `keywords`: List of important technical keywords and phrases that describe the invention.
- `claims`: List of claims of the patent (you may extract them here in addition to any separate claims call).
- `attorneys`: List of `AttorneysData` objects for any attorneys/agents of record.
- `inventors`: List of inventor names.
- `applicant`: For Google Patents, extract from the timeline/event 'Application filed by [entity]'. For Free Patents Online, extract only if applicant is explicitly present. if not present, return an empty string `""` in both cases.
- `current_assignee`: For Google Patents, List of 'Current Assignee' from the current assignee section. For Free Patents Online, list of assignee if the field present. if not present, return an empty list `[]` for both cases.
- other_ids: List of grouped key patent identifiers and classification codes. 
  Every entry is:
  - title: one of the allowed labels below.
  - value: a list of exact identifier/code strings for that label.

  Allowed title values and what to place under each:

  - `"Application Number"` — the current patent's own application/serial number.
      Google Patents: text of the top-level <dd itemprop="applicationNumber">.
      FPO: value div following label "Application Number:".

  - `"Patent Number"` — the granted patent number if the application has been issued as a patent.
      Google Patents: text of <span itemprop="representativePublication"> OR any
        granted patent number (e.g. US12579744B2) found in <dd itemprop="directAssociations">.
      FPO: value div following label "Patent Number:" if present.
      Do NOT put publication numbers (A1, A2 kind codes) here — those go under "Publication Number".

  - `"Publication Number"` — the main pre-grant publication number, e.g. `US20230377260A1`.
      Google Patents: text of the top-level <dd itemprop="publicationNumber">.
      FPO: hidden <input name="number"> value, or from the document type heading line.

  - `"Provisional Application Number"` — U.S. provisional application number, e.g. `63/344,283`.
      Google Patents: inside <tr itemprop="appsClaimingPriority"> rows where the
        applicationNumber ends with "P" OR filing date equals priority date.
      FPO: from value div following label "Parent Case Data:" — only numbers described as "provisional".

  - `"Parent Application Number"` — parent, continuation, continuation-in-part, or division parent.
      Google Patents: inside <tr itemprop="priorityApps"> rows — collect
        <span itemprop="applicationNumber"> text, EXCLUDING the current patent's own application number.
      FPO: from value div following label "Parent Case Data:" — non-provisional parent numbers
        (described as continuation, continuation-in-part, division of, etc.).

  - `"Priority Application Number"` — the application from which the current patent claims priority,
      where the priority date is strictly earlier than the current patent's own filing date.
      Google Patents: same priorityApps rows as above, filtered to those where priorityDate < filingDate.
      FPO: value div following label "Priority Application:" or any equivalent priority claim label.

  - `"Child/Family Application Number"` — applications or patents that claim priority FROM the current
      patent (children), or related family members.
      Google Patents: inside <dd itemprop="directAssociations">, collect
        <span itemprop="publicationNumber"> text (these are child/continuation applications).
        Also collect from <tr itemprop="applications"> inside <section itemprop="family">.
      FPO: value div following label "Related Child Applications:" or "Applications Claiming Priority:"
        if present.

  - `"International/PCT Application Number"` — PCT or international application number, e.g. `PCT/US2023/023096`.
      Google Patents: inside <li itemprop="application"> nested under <li itemprop="applicationsByYear">,
        collect <span itemprop="applicationNumber"> where sibling <span itemprop="countryCode"> is "WO"
        OR the number begins with "PCT/".
      FPO: value div following any label containing "PCT" or "International Application".

  - `"Classification Code"` — all CPC, IPC, USPC, Primary Class, International Class, or Other Class codes,
      e.g. `G06T17/05`, `G06F15/00`, `706/62`.
      Google Patents: inside each <li itemprop="classifications">, collect <span itemprop="Code"> text.
        ONLY include codes that are 5 or more characters (leaf codes). Skip broad parent codes like
        "G", "G06", "G06T" (fewer than 5 characters).
      FPO: combine values from ALL of these labels into one list:
        "Primary Classes:", "Other Classes:", "International Classes:", "CPC Classes:", "IPC Classes:".

  Strict rules for other_ids:
  - Group all values with the same title into one object. Never create two objects with the same title.
  - value must always be a list of strings.
  - Extract ONLY identifiers directly tied to the current patent.
  - Do NOT place in other_ids: cited patents, cited-by patents, prior art references, unrelated family
    country publications, inventor names, assignee names, dates, URLs, or status text.
  - Remove duplicate values within each value list.
  - The other_ids list must always contain all 9 title entries, even if value is [].
  - If none are found for a title, return [].

`DocumentsData` is a dictionary with the following keys:
- `url`: URL of the document.
- `source`: Human-readable name of the source (e.g. "USPTO", "Google Patents").

`AttorneysData` is a dictionary with the following keys:
- `name`: Name of the attorney or agent.
- `registrationNumber`: Registration number of the attorney in the country in which they are registered (if not present, use an empty string).

Return **only** the final JSON object, with no explanations or comments.
"""

CLAIM_ISOLATOR = """
I am providing all the content from all documents related to a patent below.
Extract all the claims from the documents.
Return the claims in the following format:
{
  "claims": "<list[str]: List of claims of the patent>",
}
Do not include any other text or comments.
"""

INFRINGEMENT_ANALYZER = """
I am providing you with 2 sets of claims :
Reference Claims: <list[str]: List of claims of the patent>
Infringing Claims: <list[str]: List of claims of the patent>
Analyze the claims and determine if the infringing claims are similar to the reference claims.
Return the analysis in the following format:
{
  "claim": "<string: Claim that is similar to the reference claims>",
  "similarity_score": "<number: Similarity score between 0 and 1>",
}
Similarity score is a number between 0 and 1 that represents the similarity between the infringing claim and the reference claim.
The higher the similarity score, the more similar the claims are.
The similarity score is calculated using the cosine similarity algorithm.
Do not include any other text or comments.

Reference Claims : 
<reference_claims_replacement>

Context of the reference claims :
<context_of_reference_claims_replacement>

Infringing Claims : 
<infringing_claims_replacement>
"""

SEARCH_STRING_GENERATOR = """
I am providing you with a list of keywords and a list of owners.
Generate a search string that will be used to search for products related to the keywords and owners.
The search string should be a valid Google Search string.
The result of the google search should yield product pages, product manuals, technical documentation, support pages, reviews, screenshots, videos, or other product evidence pages.
The result of the google search should not be another search results page.
For product infringement analysis, companies listed under "Companies to focus search on" are the accused-product companies/products to search for. Do not exclude them.
Do not replace accused-product companies with the patent owner unless the keywords explicitly ask for the patent owner's products.
If owners are provided, treat them as reference patent owners. Do not assume the owner's products are the accused products.
Prioritize the accused product/company, product behavior, manuals, technical documentation, and UI evidence.
The search string should be a single string, not a list of strings.
Return only raw JSON. Do not wrap the JSON in Markdown fences.

Return the search string in the following format:
{
  "search_string": "<string: Search string>",
}

Keywords: <keywords_replacement>

Owners: <owners_replacement>

Companies to focus search on: <search_limitations_companies>

Websites to focus search on: <search_limitations_websites>
Do not include any other text or comments.
"""

PERFORM_GOOGLE_SEARCH_PROMPT = """
I am providing you with a search string.
Perform a google search with the search string.
Return the results in the following format:
{
  "results": [
    {
      "title": "<string: Title of the result>",
      "url": "<string: URL of the result>",
      "website_name": "<string: Name of the website of the result>",
      "description": "<string: Description of the result>",
    }
  ]
}
Do not include any other text or comments.
The results should be product evidence pages: product pages, manuals, technical documentation, support pages, reviews, screenshots, videos, or pages describing accused product behavior. They do not need to be purchase/order pages.
Return only raw JSON. Do not wrap the JSON in Markdown fences.

Here's is the search string to perform the google search:
<search_string_replacement>
"""

PRODUCT_DETAILS_EXTRACTOR = """
I am providing you with the content of a product page from a relevant source.
Extract the essential details of the product from the content.
Return the details in the following format:
{
  "product_details": [
    {
      "source": "<string: Source of the product details>",
      "product_id": "<string: ID of the product>",
      "product_url": "<string: URL of the product>",
      "product_name": "<string: Name of the product>",
      "claims": "<list[str]: List of claims of the product>"
    }
  ]
}
Do not include any other text or comments.
"""

PRODUCT_INFRINGEMENT_ANALYZER = """
I am providing you with 2 sets of claims :
Reference Claims: <list[str]: List of claims of the patent>
Infringing Claims: <list[str]: List of claims of the patent>
Analyze the claims and determine if the infringing claims are similar to the reference claims.
Return the analysis in the following format:
{
  "items": [
    {
      "claim": "<string: Claim that is similar to the reference claims>",
      "similarity_score": "<number: Similarity score between 0 and 1>",
      "source": "<string: Source of the product details>",
      "url_to_claim": "<string: URL to the claim>",
      "justification": "<string: Justification for the similarity score>"
    }
  ]
}
Similarity score is a number between 0 and 1 that represents the similarity between the infringing claim and the reference claim.
The higher the similarity score, the more similar the claims are.
The similarity score is calculated using the cosine similarity algorithm.
Do not include any other text or comments.

Reference Claims : 
<reference_claims_replacement>

Context of the reference claims :
<context_of_reference_claims_replacement>

Infringing Claims : 
<infringing_claims_replacement>
"""
