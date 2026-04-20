# RetailGPT

AI-powered sales intelligence assistant for Area Sales Managers (ASMs) and Regional Sales Managers (RSMs) at an Indian consumer goods company.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=sb_publishable_...   # or the legacy anon key
UPLOAD_PASSWORD=your_secret_password

# Optional — add for 10× faster data loading with 900k rows:
# SUPABASE_DB_URL=postgresql://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

### 3. Create Supabase tables

Open the **SQL Editor** in your Supabase dashboard and run:

**Access control table (run this first):**

```sql
CREATE TABLE IF NOT EXISTS approved_users (
    id         BIGSERIAL PRIMARY KEY,
    email      TEXT UNIQUE NOT NULL,
    role       TEXT NOT NULL,
    name       TEXT NOT NULL,
    active     BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now()
);
```

After creating the table, insert at least one Master user so you can log in:

```sql
INSERT INTO approved_users (email, role, name)
VALUES ('your@email.com', 'Master', 'Admin');
```

**Sales data tables:**

```sql
-- outlet_data table
CREATE TABLE IF NOT EXISTS outlet_data (
    id              BIGSERIAL PRIMARY KEY,
    area            TEXT,
    sales_officer   TEXT,
    distributor     TEXT,
    distributor_erpid TEXT,
    zone            TEXT,
    state           TEXT,
    beats_or_route  TEXT,
    shop_erpid      TEXT,
    outlet          TEXT,
    product_name    TEXT,
    date            DATE,
    day             INTEGER,
    year            INTEGER,
    month           INTEGER,
    week            INTEGER,
    month_week      TEXT,
    order_in_unit   NUMERIC(12,2),
    net_value_order NUMERIC(14,2),
    rsm             TEXT,
    asm             TEXT,
    l1_parent_category TEXT,
    fy              TEXT DEFAULT 'FY25'
);

CREATE INDEX IF NOT EXISTS idx_outlet_date       ON outlet_data(date);
CREATE INDEX IF NOT EXISTS idx_outlet_so         ON outlet_data(sales_officer);
CREATE INDEX IF NOT EXISTS idx_outlet_asm        ON outlet_data(asm);
CREATE INDEX IF NOT EXISTS idx_outlet_rsm        ON outlet_data(rsm);
CREATE INDEX IF NOT EXISTS idx_outlet_month_year ON outlet_data(year, month);
CREATE INDEX IF NOT EXISTS idx_outlet_fy         ON outlet_data(fy);

-- targets table
CREATE TABLE IF NOT EXISTS targets (
    id            BIGSERIAL PRIMARY KEY,
    rsm_name      TEXT,
    asm_name      TEXT,
    so_name       TEXT,
    secondary_tgt NUMERIC(14,2),
    upc_target    NUMERIC(10,2),
    month         INTEGER,
    year          INTEGER
);

CREATE INDEX IF NOT EXISTS idx_targets_so  ON targets(so_name);
CREATE INDEX IF NOT EXISTS idx_targets_asm ON targets(asm_name);
CREATE INDEX IF NOT EXISTS idx_targets_my  ON targets(month, year);
```

> The same SQL is also available in the Upload page under "First-time Setup."

### 4. Upload data

Go to `http://localhost:8501/upload` → enter your `UPLOAD_PASSWORD` → upload `OutletFY25.xlsx` and the target file.

### 5. Run the app

```bash
streamlit run app.py
```

---

## File Structure

```
RetailGPTFinal/
├── app.py              # Main Streamlit chat UI (no login required)
├── pages/
│   └── upload.py       # Password-protected data upload page
├── query_engine.py     # Core logic: question → pandas → formatted answer
├── fuzzy_matcher.py    # Fuzzy name matching (rapidfuzz)
├── supabase_client.py  # Supabase connection, caching, upload helpers
├── metrics.py          # All metric calculations + Indian number formatting
├── prompts.py          # All prompt engineering — the "brain" file
├── requirements.txt
├── .env.example
└── README.md
```

---

## Metrics Reference

| Metric | Definition |
|--------|-----------|
| Secondary | SUM(Net Value Order) |
| TC | COUNT(all rows) |
| PC | COUNT(rows where Net Value Order > 0) |
| UPC | COUNT DISTINCT(Shop ERPID where Net Value Order > 0) |
| ABV | Secondary ÷ PC |
| Secondary Ach% | (Secondary ÷ Secondary Target) × 100 |
| UPC Ach% | (Achieved UPC ÷ UPC Target) × 100 |

---

## Time Periods

| Label | Definition |
|-------|-----------|
| MTD | 1st of month → latest date **in the data** (not system date) |
| LMTD | 1st of last month → same day-of-month as latest data date |
| 3M | Last 3 complete calendar months |
| YTD | April 1 of current FY → latest data date |

---

## Sales Hierarchy

```
RSM (Regional Sales Manager)
 └── ASM (Area Sales Manager)
      └── SO (Sales Officer)
           └── Beat / Route
                └── Outlet
```

4 regions: North, South, East, West. RSM may be "Vacant" in some regions.

---

## Fuzzy Name Matching

- **> 90% match** — auto-corrected silently, answer given
- **70–90% match** — asks "Did you mean [name]?" before answering
- **< 70% match** — lists closest options, asks user to clarify
- **Multiple equal matches** — asks "Which [name]? — Person A (ASM, South) or Person B (ASM, North)?"

---

## Performance Notes

- With 900k rows via REST API: ~30–60s first load, then cached for 1 hour.
- **For production**: add `SUPABASE_DB_URL` to `.env` for direct PostgreSQL access — reduces load time to ~3–5s.
- Click **⟳ Refresh Data** in the chat UI to force a cache reload after uploading new files.

---

## Multi-FY Support

From April 2026 onwards, upload `OutletFY26.xlsx`. The `fy` column in `outlet_data` ensures both FY25 and FY26 data can coexist in the same table. Queries automatically search across all FY data.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_KEY` | ✅ | Supabase publishable/anon key |
| `UPLOAD_PASSWORD` | ✅ | Password for the upload page |
| `SUPABASE_DB_URL` | Optional | Direct PostgreSQL URL for faster bulk loads |
