# Patent Gap AI — User Manual

A step-by-step guide to using Patent Gap AI from your first visit through everyday infringement monitoring.

## Table of Contents

1. [The Home Page](#1-the-home-page)
2. [Creating an Account](#2-creating-an-account)
3. [Signing In](#3-signing-in)
4. [The Dashboard](#4-the-dashboard)
5. [Adding a Patent — by Patent ID (USPTO / EP / WO)](#5-adding-a-patent--by-patent-id-uspto--ep--wo)
6. [Adding a Patent — by Local Upload](#6-adding-a-patent--by-local-upload)
7. [The Patent Detail Page](#7-the-patent-detail-page)
8. [Editing Patent Details](#8-editing-patent-details)
9. [Running the Infringement Analysis](#9-running-the-infringement-analysis)
10. [Reviewing Potential Matches](#10-reviewing-potential-matches)
11. [Notifications](#11-notifications)
12. [Your Profile](#12-your-profile)
13. [Signing Out](#13-signing-out)
14. [Reference — What the Colours, Badges, and Percentages Mean](#14-reference--what-the-colours-badges-and-percentages-mean)

---

## 1. The Home Page

When you arrive at Patent Gap AI you'll land on the marketing home page. It has the following sections, all reachable from the top navigation:

- **Opportunity** — why portfolio monitoring matters.
- **How It Works** — the 4-step process: claims analyzed → technologies monitored → infringements identified → attorneys review.
- **Attorneys** — how the platform fits legal workflows.
- **Early Access** — current beta status.
- **Testimonials** — feedback from beta partners.

In the **top-right** of the navbar you'll see three buttons (when signed out):

- `Login` — go to the sign-in page.
- `Contact Us` — open the contact form.
- `Request Demo` — open the demo request form.

At the bottom of the page is a final **Get Started** call-to-action with two buttons that lead to **Request Early Access** and **Contact Us**.

Use one of the **Request Demo** or **Contact Us** buttons if you don't yet have access, or click **Login** if you've already been onboarded.

---

## 2. Creating an Account

Click **Login** at the top → on the login page, click **Register** at the bottom of the form. The registration is split into 3 steps.

### Step 1 — Identity

- **Profile Picture** *(optional)* — JPG/PNG/WEBP, max 5 MB.
- **Title** (required) — Mr / Ms / Mx / Dr / Prof.
- **Full Name** (required).
- **Work Email** (required).
- **Job Title** (required) — e.g. "Patent Counsel".
- **Company / Firm** *(optional)*.
- **Phone** *(optional)*.

Click **Continue** to move to Step 2.

### Step 2 — Security

- **Password** (required, minimum 8 characters).

  As you type, you'll see a strength meter with five colour-coded bars:

  | Strength  | Bar colour  |
  | --------- | ----------- |
  | Very weak | Red         |
  | Weak      | Orange      |
  | Fair      | Yellow      |
  | Good      | Light green |
  | Strong    | Brand green |

  You must reach at least **Fair** to continue.

- **Confirm Password** (required) — must match. You'll see a green ✓ or red ✗ underneath.

A note at the bottom explains that the platform also silently captures your timezone, locale, platform, and IP address in the background — you don't need to enter these.

### Step 3 — Address & Terms

All address fields (Line 1, Line 2, City, State/Region, Postal Code, Country) are *optional*.

Tick the **I agree to the Terms of Service and Privacy Policy** checkbox. Clicking the underlined link opens the Beta Agreement PDF in a modal viewer. You must accept the terms to proceed.

Click **Create Account**. When it succeeds, you'll be automatically signed in and redirected to your dashboard.

---

## 3. Signing In

On the **Login** page:

1. Enter your **Work Email**.
2. Enter your **Password** (toggle the eye icon to show/hide).
3. Click **Sign In**.

If the backend is cold-starting, you'll see the button text change to *"Waking up server, please wait…"*. This is normal — wait a few seconds.

If sign-in fails, an error banner appears at the top of the form with the reason (wrong password, account not found, etc.).

On success you're taken straight to the **Dashboard**.

---

## 4. The Dashboard

This is your main workspace. The layout is:

### Sidebar (left)

The sidebar contains:

- **MAIN**
  - **Dashboard** — the page you're on.
  - **Monitoring** — *not yet implemented (you'll see "Under development" on hover).*
  - **Findings** — *not yet implemented.*
- **ANALYSIS**
  - **Reports** — *not yet implemented.*
  - **History** — *not yet implemented.*
- **ACCOUNT**
  - **Profile** — opens your profile page.
  - **Settings** — *not yet implemented.*
  - **Report Bug** — opens a Google Form in a new tab.

Your name, role and avatar are shown at the bottom of the sidebar. Clicking that block also takes you to your **Profile**.

On mobile, tap the hamburger icon in the top bar to open the sidebar.

### Top Bar

- **Search box** (centre) — filters your patents by title or patent number in real time. Click the "×" to clear.
- **Notification bell** (right) — see [Notifications](#11-notifications).
- **Home** button — returns to the marketing home page.
- **Log out** button — signs you out and returns to the login page.

### High-Risk Alert Banner

If you have any HIGH-risk findings, a red alert banner appears at the top of the content area:

> ⚠ **N HIGH risk findings** require attorney review — potential infringement detected.

Click the **×** to dismiss it for the session.

### Stat Cards (clickable filters)

Four cards summarise your portfolio. **Click any card to filter the patent list below to only that category. Click again to clear the filter.** The active card is highlighted.

| Card                                       | What the number on the card means                                                                     | What clicking it filters to                                  |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| **Active Scans** (blue, magnifier icon)    | Patents currently being processed by the backend (`current_status = processing`).                     | Patents with status **Patented**.                            |
| **Patents Analyzed** (purple, document icon) | Patents that have completed analysis or already have at least one infringement.                     | The full portfolio.                                          |
| **High Risk Matches** (yellow, warning icon) | Patents whose overall overlap score is in the HIGH band (> 90%).                                     | Patents with status **Patented**.                            |
| **Cleared Patents** (green, check icon)    | Patents with no infringements found, or no analysis run yet.                                          | Patents with status **complete / cleared / expired / abandoned**. |

> Note: the **count** displayed on each card is computed on the server using the rules in the middle column, while the **filter** triggered by clicking is purely client-side using the rules in the right column. These may not always agree — for example, a patent listed under "Active Scans" on the server may not appear when you click that card if its status isn't "Patented". This is a known limitation.

When a filter is active, a **Clear filter** pill appears in the top-right of the page header.

### Page Header — Buttons

- **Export** — button is present but no export endpoint is wired up on the backend yet, so clicking it currently does nothing usable.
- **Add Patent** — opens the **New Patent Analysis** modal (see [section 5](#5-adding-a-patent--by-patent-id-uspto--ep--wo)).

### Active Patents Grid

Each patent is shown as a **Project Card** containing:

- **Status badge** (top-left) — see the colour reference in [section 14](#14-reference--what-the-colours-badges-and-percentages-mean).
- **Risk badge** if applicable — *High Risk* (red) or *Med Risk* (amber).
- **NEW "Updates" pill** — a small pulsing green badge that means the patent has been updated since your last visit.
- **Analysis Status Icon** — a red triangle (⚠) means the infringement analysis is still incomplete.
- **Title** of the patent.
- **Patent number**.
- **Overlap Score** — the percentage and 5-dot indicator showing how much your patent overlaps with detected infringements. Coloured by risk.
- **Time ago** — e.g. "3 hours ago".
- **Matches count** — number of potential infringement matches found (in amber).
- **"Open in new view" button** (top-right) — opens the patent detail page.

Click anywhere on a card to open its **Patent Detail Page**.

The grid loads more patents automatically as you scroll (infinite scroll). When you reach the end, you'll see "End of list".

### Weekly Search Card

Below the patent grid, when no filter is active, a **Weekly Search Results** card shows the last automated scan timestamp and the count of new results found. This is a system-wide weekly scan, separate from individual patent analysis.

### Section Header Actions

- **Refresh button** (circular arrow) — re-pulls patents and stats from the server.
- **View All** — clears any filter or search and shows all patents.

---

## 5. Adding a Patent — by Patent ID (USPTO / EP / WO)

This is the **fastest** path: enter a patent number and we fetch everything automatically.

1. From the dashboard, click **+ Add Patent** (top right).
2. The **New Patent Analysis** modal opens with two tabs at the top: **Upload File** and **Patent ID**. Click **Patent ID**.
3. Enter the patent number in the **Patent Number** field, e.g. `US10203040B2`.

   **Supported formats:**

   | Type         | Examples                            |
   | ------------ | ----------------------------------- |
   | US Granted   | `US10203040B2`, `US-10203040-B2`    |
   | US Pre-grant | `US20240412550A1`                   |
   | EP Patents   | `EP1234567`, `EP-1234567-A1`        |
   | WO Patents   | `WO2023123456`                      |

4. Click **Fetch & Create Patent**.

The system runs three steps in sequence, shown live with a checklist of green checkmarks:

1. **Fetching from USPTO** — pulling the patent record.
2. **Generating description** — if the patent description is too short, an AI summary is created.
3. **Isolating claims** — extracting the patent's claims.

When all three finish, the modal closes and you're taken to the **Patent Detail Page** for that patent.

> Note: This path does **not** run the infringement analysis automatically. To start the analysis, click **Run Analysis** on the detail page (see [section 9](#9-running-the-infringement-analysis)).

> If a patent isn't found on USPTO, the backend falls back to Google Patents (and, where wired up, Free Patents Online) to enrich the data. This is transparent — you'll just see the source name change on the detail page.

---

## 6. Adding a Patent — by Local Upload

Use this when your patent isn't in a public database or you have a PDF you want to analyse.

1. From the dashboard, click **+ Add Patent**.
2. The modal opens on the **Upload File** tab by default.
3. Fill in **Step 1 of 2 — Upload Patent**:
   - **Project Name** (required) — e.g. "Foldable Display Hinge Analysis".
   - **Patent ID** (required) — your own identifier (e.g. `US1234`). It will be stored as `local_US1234`.
   - **PDF file** (required) — click the dropzone to browse, or drag and drop. **Max 12 MB**, PDF only. (The dropzone only accepts `.pdf`; XML uploads are supported elsewhere — see the **Add Document** flow in [section 7](#7-the-patent-detail-page).)
   - **Keywords** *(optional)* — comma-separated, e.g. "AI, Machine Learning, Neural Networks".
   - **Filing Date** *(optional)* — must be between 1950-01-01 and today.
   - **Status** *(optional)* — choose from: Aborted, Patented, Expired, Payment Pending, Rejected, Withdrawn, Processing.
   - **Inventors** *(optional)* — comma-separated.
4. Click **Continue** to move to **Step 2 of 2 — Add Context**.
5. In Step 2:
   - **Patent Reference** is shown as a read-only confirmation.
   - **Captured Details** summarise what you entered in Step 1.
   - **Context Description** — describe the core novelty, defensive goals, or specific technical elements the AI should focus on. The more specific, the better the analysis.
   - Two **AI Refinement Questions** are shown for your awareness (informational).
6. Click **Start creating patent**.

While the patent is being created you'll see:

- *Creating Patent…*
- *Uploading File…*

When complete, you're taken to the **Patent Detail Page**.

> Click **Back** to revisit Step 1 (you'll be warned that progress will be lost) or **Cancel** to abandon the modal entirely.

---

## 7. The Patent Detail Page

The detail page is organised top-to-bottom into the following sections.

### Top Action Bar

- **Back** — return to the previous page.
- **Export** — button is present, but the backend doesn't expose an export endpoint yet, so this is currently a placeholder.
- **Run Analysis** — start a fresh infringement analysis (only visible when no analysis is already running on the backend).

### Hero Patent Card

Shows the patent's **status pill**, **source name** (US Patent Office / Espacenet / Google / Manual Entry / Patent Gap), **title**, **patent number**, **time since last update**, and the **matches count** (in amber if > 0).

### Case Information (left column)

Read-only details: Created date, Filed date, Last Updated, Inventors, Keywords, Source.

### Context & Description (right column) — Editable

This is the main free-text description. Hover over it and click the **pencil icon** in the top-right to edit. Inside the editor:

- Type your new description.
- Keyboard shortcuts: **Ctrl+Enter** to save, **Esc** to cancel.
- Click **Save** or **Cancel**.

Below the description you may also see **Search Strategy** chips showing target companies and search terms, if any were captured.

### Search Limitations — Editable

Restrict the analysis to certain companies, keywords, or URLs. The analysis will *exclude* matches that come from these constraints (or focus on them, depending on the API behaviour).

- **Companies** — type a name and press **Enter** or **comma** to add it as a tag. Only letters, numbers, spaces and `- _ . &` are allowed.
- **Keywords / Terms** — same input style.
- **Reference URLs** — accepts `www.domain.tld`, `https://domain.tld`, or `domain.tld`. Invalid URLs show an inline red error.

Click **×** on any tag to remove it. Click **Save** to persist, **Cancel** to revert.

### Related IDs

If the patent has linked entries in other patent families (e.g. priority applications, continuations), they're listed here as pill chips, grouped by ID type. This section is read-only.

### Documents

The grid shows one thumbnail per attached document. Each thumbnail displays a source-specific image (USPTO, Espacenet, Google Patents, Freepatentsonline, Local, etc.), the index number, the source name, and the file extension.

- **Add Document** (top-right of the section) — uploads a new file to the case. The backend accepts **PDF or XML** only, with a maximum file size of **12 MB**. Files outside these limits are rejected with an error message.
- Clicking a thumbnail opens it:
  - **USPTO** and **Local** documents open inside an in-app **Document Modal** with previous/next navigation.
  - Anything else opens in a new browser tab.

### Claims for Analysis — Editable

The list of patent claims used by the AI. Hover the section and click the **pencil icon** to enter edit mode. In edit mode you can:

- Re-write any claim text.
- **Move a claim up/down** with the chevron buttons.
- **Remove** a claim with the × button.
- **Add Claim** to append a new empty one.
- Keyboard: **Ctrl+Enter** to save, **Esc** to cancel.
- Click **Save Claims** when done.

### Claims Chart

When analysis has completed, each of your claim numbers is shown alongside coloured pill-borders for every infringement that overlaps it. Pill colour follows the standard:

- **Red** — ≥ 90% similarity
- **Orange** — 70–89% similarity
- **Green** — < 70% similarity

### Potential Matches

The heart of the analysis. See [section 10](#10-reviewing-potential-matches).

### Bottom Action Buttons

- **Export Case** — placeholder button; no backend export endpoint is wired up yet.
- **Delete Case** — currently **non-functional**. The UI asks for confirmation and dispatches a delete, but the backend does not expose a `DELETE /api/cases/<id>` route, so the call will fail. The card may temporarily disappear from your local list, but it is **not actually removed on the server** and will return on refresh.

---

## 8. Editing Patent Details

Most editable fields use the same pattern: hover the section, click the **pencil icon** (top right of that section), make your changes, then press **Save** (or **Ctrl+Enter**). **Esc** cancels.

You can edit:

- **Title** — not directly editable from the UI; the displayed title comes from the patent record fetched from USPTO/Google Patents (or the **Project Name** you entered for a local upload).
- **Description / Context** — Context & Description card.
- **Claims** — Claims for Analysis card.
- **Search Limitations** — Companies, Keywords, Reference URLs.
- **Documents** — add new files; the section's *Add Document* button opens a file picker (PDF or XML, ≤ 12 MB).

All edits are persisted via the backend's `update-patent` endpoint. If a save fails, an inline red error message appears with the reason.

---

## 9. Running the Infringement Analysis

From the **Patent Detail Page**:

1. Make sure the patent has both **keywords** and at least one **document**. If either is missing you'll see *"Cannot run analysis: missing keywords or documents."*
2. Click **Run Analysis** (top-right of the page, or via the **Start Analysis** button when there are no matches yet).
3. You'll see a spinner with either:
   - *Isolating Claims…*
   - *Finding Infringements…*

While the analysis runs on the backend, the page **polls every 15 seconds** for updates. You can leave the page and come back — the analysis continues server-side.

### Analysis Statuses

The backend exposes the current step of the analysis through the `infringement_analysis_status` field on the case. The Potential Matches section reflects this with the following states:

| Backend status                       | What it means                                                                                       | What you see                                                                                       |
| ------------------------------------ | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `Started`                            | The analysis has just begun and is searching patent sources.                                        | Amber spinner card with "Processing" pill. Re-run buttons hidden.                                  |
| `Patent Sources Completed`           | Patent-source search has finished; product-source search is now running.                            | Same spinner card (still in progress).                                                             |
| `Product Sources Completed`          | Both patent and product searches have finished writing infringements.                               | Spinner card on the way to **Completed**.                                                          |
| `Completed`                          | The analysis run is fully done.                                                                     | Either the grid of match cards (matches found) or a green ✓ panel with **Start Analysis** button. |
| `Failed during Patent Sources`       | An error occurred while searching patent sources.                                                   | The detail page shows an error and a re-run button.                                                |
| `Failed during Product Sources`      | Patent search succeeded but product search threw an error. Any patent matches found are kept.       | The detail page shows an error and a re-run button.                                                |

While the analysis runs, the page polls every 15 seconds for status changes. Once finished, a small **refresh button** (top right of the Potential Matches section) lets you re-run the analysis on demand.

---

## 10. Reviewing Potential Matches

Each potential infringement is shown as a **Match Card** in a 3-column grid (1 column on mobile).

### What's on each Match Card

- **Risk badge** (top-left) — High Risk (red), Med Risk (amber), or Low Risk (green).
- **Type pill** (top-right):
  - **📄 Patent** (green) — another patent that overlaps yours.
  - **🛒 Product** (amber) — a real-world product (e.g. from Amazon) that may infringe.
- **Title** of the matching patent or product.
- **ID** — `Patent: …` or `Product: …`.
- **Company** (for patents) — when known.
- **Claim snippet** (for products) — the first ~80 characters of the closest claim.
- **Overlap Score** with a coloured progress bar (see the colour reference below).
- **Time ago** stamp.
- **Exclude** button (red, bottom-right) — see below.

### Clicking a match

Click the card body (or the open-in-window icon) to open the **Infringement Detail Modal**.

### The Infringement Detail Modal

At the top of the modal you'll see:

- A **type pill** (📄 Patent or 🛒 Product).
- A **case chip** (your patent's case number).
- The entry/product ID.
- A **risk pill** showing both the risk level (`HIGH RISK · 92%`) and the overall overlap percentage.

If the match looks suspiciously similar to your own patent (e.g. the same patent re-filed in a different database), a yellow warning banner appears: *"Note: This infringement might be the same patent, but filed on a different database."*

Below that you'll see:

- **Source** and **Entry ID** cards.
- **Product Claims** (for product matches).
- A large **Overlap Score** bar with the percentage in big serif type, coloured by risk.
- A **Visit Infringement Source / Visit Product Listing** button — opens the original URL in a new tab.

#### Side-by-Side Claim Chart

A table comparing your patent's claims to the infringing ones. Columns:

| Column                                                     | What it shows                                                                                            |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Claim #                                                    | Sequential number.                                                                                       |
| Your Patent Claim / Product Claim / Reference Claim        | The text of your claim (or product claim for product matches).                                           |
| Similar Infringing Claim / Matched Claim                   | The corresponding text in the infringement, with a "View source →" link when available.                  |
| Similarity                                                 | A coloured percentage chip: red (high), orange (medium), green (low).                                    |
| Justification                                              | (Products only) the AI's reasoning for why this product claim infringes.                                 |

At the bottom:

- **Close** — close the modal.
- **Export Report** — placeholder button; no backend export endpoint exists yet.

### Excluding a match

If a match is irrelevant (e.g. your own patent on a different database, or a false positive), click **Exclude** on the match card. After confirming the prompt, the match is removed from the list and the case is updated on the backend.

---

## 11. Notifications

The bell icon in the top bar shows a **green counter badge** when patents have been updated since your last visit (e.g. new infringements found by automated weekly scans).

Click the bell to open a dropdown listing each updated patent:

- A pulsing green dot indicates the update.
- The patent **title** and **patent number** are shown.
- An **updatedAt** timestamp.
- A risk pill if the patent is high or medium risk.

Click any row to jump straight to that patent's detail page. The badge clears once you visit the patent (the visit timestamp is persisted via the `update-patent` endpoint).

> The "updates since last visit" logic is driven by comparing each patent's `last_updated` with your local `last_viewed` timestamp; there is no dedicated notifications service or push channel on the backend. Updates therefore only appear after you refresh or reload the dashboard.

---

## 12. Your Profile

Open via the sidebar's **Profile** entry, the avatar block at the bottom of the sidebar, or the **Profile** link in the top navbar.

### Identity Card (left column)

- Profile photo with a **camera button** to upload a new one (any image format).
- Your name, role tag (job title), and company.
- A **Quick stats** strip (Patents / Findings / Reports) — *placeholders for now.*

### Tabs

There are two working tabs:

#### Account tab

Edit your personal and address information:

- **Personal** — Title, Full Name, Work Email, Job Title, Company / Firm, Phone.
- **Address** *(optional)* — Address Line 1, Address Line 2, City, State / Province, Postal Code, Country.

Click **Save Changes**. A green "Changes saved" pill confirms success.

#### Security tab

- **Change Password**
  - Enter your **Current Password**, **New Password** (min 8 characters), and **Confirm New Password**. Use the eye icons to toggle visibility.
  - Click **Update Password**. A green "Password updated" pill confirms.
  - If the new passwords don't match or are too short, you'll see an inline red error.
- **Session & Access** — read-only info: Account Status (Active, green pill), Last Sign In, Access Level (your job title), Encryption (TLS 1.3), SOC 2 (Compliant).
- **Danger Zone** — a red-bordered **Delete Account** button. There is **no backend endpoint** to delete an account, and the button has no handler attached — clicking it currently does nothing.

> The **Notifications** tab in the sidebar is not currently exposed — only the Account and Security tabs are active in this build. There is no backend storage for notification preferences either.

---

## 13. Signing Out

You can sign out from three places:

- The **Log out** button in the dashboard's top bar.
- The **Log out** button in the patent detail page's top bar.
- The **Sign Out** entry at the bottom of the Profile sidebar.
- The **Logout** button in the main navbar (when signed in and viewing public pages).

After signing out you're redirected to the **Login** page. All local session data is cleared, so you'll need to sign in again to access any protected page.

---

## 14. Reference — What the Colours, Badges, and Percentages Mean

### Overlap Score & Risk Level

The platform computes an **Overlap Score** for every infringement (and an averaged score for the whole patent). It's a percentage between 0 and 100. The backend's risk classifier (`get_risk_level`) uses these exact thresholds on the average similarity score (0.0 – 1.0):

| Overlap Score   | Risk Level | Colour              | Meaning                                                              |
| --------------- | ---------- | ------------------- | -------------------------------------------------------------------- |
| **> 90 %**      | **HIGH**   | 🔴 Red              | Very strong overlap — likely infringement, prioritise attorney review. |
| **> 70 %** to ≤ 90 % | **MEDIUM** | 🟠 Amber / Orange | Substantial overlap — worth investigating.                           |
| **0 – 70 %**    | **LOW**    | 🟢 Green            | Weak overlap — informational.                                        |

This colour code applies to:

- The risk badge on every patent card and match card.
- The progress bar inside each card.
- The overlap percentage in the Infringement Detail modal.
- The pill border on the Claims Chart.
- The dashboard's red **HIGH risk findings** alert banner.

### Patent Status Colours

| Status         | Badge colour       | Meaning                                                                |
| -------------- | ------------------ | ---------------------------------------------------------------------- |
| **Patented**   | 🟢 Green           | Active, granted patent under monitoring.                               |
| **Expired**    | 🔴 Red             | Patent term has expired.                                               |
| **Abandoned**  | ⚪ Grey / amber    | Patent prosecution was abandoned or withdrawn.                         |
| **Processing** | (no specific colour) | The patent is still being created / claims still being isolated.     |

### Match Type Pills

| Pill           | Colour | What it represents                                          |
| -------------- | ------ | ----------------------------------------------------------- |
| **📄 Patent**  | Green  | The match is another patent filing.                         |
| **🛒 Product** | Amber  | The match is a real-world product (e.g. Amazon listing).    |

### Other Visual Cues

- **Updates pill** (green, pulsing) on a patent card — the patent has changed since you last viewed it.
- **Analysis Status Icon** (red ⚠) on a patent card — the infringement analysis is incomplete or was stopped.
- **Bell counter badge** (green) — unread updates exist; the number is the count of patents with updates.
- **Live dot** (small green pulsing circle) — used as a visual marker on section headers to indicate "live monitoring".
- **High-risk alert banner** (red, top of dashboard) — at least one patent has reached the HIGH risk threshold. Dismiss with **×**.

### Password Strength Bars (Registration only)

| Bars filled | Label     | Colour      |
| ----------- | --------- | ----------- |
| 1           | Very Weak | Red         |
| 2           | Weak      | Orange      |
| 3           | Fair      | Yellow      |
| 4           | Good      | Light green |
| 5           | Strong    | Brand green |

You need **Fair** or higher to advance.

---

## End

That's the complete user flow for the features currently shipped in Patent Gap AI. Sections like **Monitoring**, **Findings**, **Reports**, **History**, and **Settings** show "Under development" tooltips and aren't covered in this manual yet — they'll be added once they go live.

If you hit any issue, use the **Report Bug** link in the sidebar — it opens a Google Form you can fill in directly.
