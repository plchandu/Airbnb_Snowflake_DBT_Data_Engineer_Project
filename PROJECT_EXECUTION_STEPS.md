# 🚀 Airbnb Snowflake & dbt Data Engineering Project: End-to-End Execution Guide

A comprehensive, step-by-step operational guide detailing every phase, terminal command, and SQL script required to build and execute the Airbnb data pipeline from raw source files to production-grade Medallion analytics in Snowflake.

---

## 📑 Table of Contents
1. [Architecture & Pipeline Overview](#1-architecture--pipeline-overview)
2. [Phase 1: Environment & Dependency Setup](#2-phase-1-environment--dependency-setup)
3. [Phase 2: Snowflake Infrastructure Setup](#3-phase-2-snowflake-infrastructure-setup)
4. [Phase 3: Raw Data Ingestion (Staging Layer)](#4-phase-3-raw-data-ingestion-staging-layer)
5. [Phase 4: dbt Profile Configuration & Connection Test](#5-phase-4-dbt-profile-configuration--connection-test)
6. [Phase 5: Step-by-Step dbt Transformation Execution](#6-phase-5-step-by-step-dbt-transformation-execution)
   - [5.1 Bronze Layer (Raw Ingestion)](#51-bronze-layer-raw-ingestion)
   - [5.2 Silver Layer (Transformation & Enrichment)](#52-silver-layer-transformation--enrichment)
   - [5.3 Gold Layer (OBT & Fact Models)](#53-gold-layer-obt--fact-models)
   - [5.4 Snapshots (SCD Type 2 Dimension Tracking)](#54-snapshots-scd-type-2-dimension-tracking)
7. [Phase 6: Data Quality Testing & Governance](#7-phase-6-data-quality-testing--governance)
8. [Phase 7: Lineage & Documentation Generation](#8-phase-7-lineage--documentation-generation)
9. [Phase 8: One-Shot Build & Maintenance Commands](#9-phase-8-one-shot-build--maintenance-commands)
10. [Troubleshooting & FAQs](#10-troubleshooting--faqs)

---

## 1. Architecture & Pipeline Overview

```
┌─────────────────┐      ┌─────────────────────────┐      ┌────────────────────────────────────────────────────────┐
│  Source CSVs    │      │    Snowflake Staging    │      │               dbt Medallion Layers                     │
│                 │      │                         │      │                                                        │
│ • bookings.csv  │ ───► │ AIRBNB.STAGING.BOOKINGS │ ───► │ 🥉 BRONZE (bronze_*)   : Raw typed tables              │
│ • hosts.csv     │      │ AIRBNB.STAGING.HOSTS    │ ───► │ 🥈 SILVER (silver_*)   : Cleaned, validated, tagged   │
│ • listings.csv  │      │ AIRBNB.STAGING.LISTINGS │ ───► │ 🥇 GOLD   (obt, fact)  : One Big Table & Fact Tables   │
│                 │      │                         │      │ 📸 SNAPSHOTS (dim_*)   : SCD Type 2 history tracking   │
└─────────────────┘      └─────────────────────────┘      └────────────────────────────────────────────────────────┘
```

---

## 2. Phase 1: Environment & Dependency Setup

### Step 1.1: Clone and Navigate to Project
```bash
cd /Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project
```
* **Explanation**: Enters the root directory containing source data, SQL DDLs, and the dbt project folder.

### Step 1.2: Activate Python Virtual Environment
Using `uv` (or standard `venv`):
```bash
# Using uv:
uv sync

# Or standard virtual environment:
source .venv/bin/activate
```
* **Explanation**: Installs and synchronizes all dependencies (`dbt-core`, `dbt-snowflake`, `snowflake-connector-python`, `python-dotenv`, `sqlfmt`) specified in `pyproject.toml`.

### Step 1.3: Set Environment Variables for Security
Create or edit your `.env` file in the project root:
```bash
cat << 'EOF' > .env
SF_PWD=YourSnowflakePasswordHere
EOF
```
* **Explanation**: Prevents credentials from being committed to Git. The `.env` file is already excluded in `.gitignore`.

---

## 3. Phase 2: Snowflake Infrastructure Setup

Execute the following SQL commands in the **Snowflake Snowsight UI Worksheet** or via **Snowflake CLI (`snow sql`)** as `ACCOUNTADMIN`:

```sql
-- 1. Create compute warehouse
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WHS
  WITH WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 300
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- 2. Create the target Database
CREATE DATABASE IF NOT EXISTS AIRBNB;

-- 3. Create required Schemas
USE DATABASE AIRBNB;
CREATE SCHEMA IF NOT EXISTS STAGING;
CREATE SCHEMA IF NOT EXISTS BRONZE;
CREATE SCHEMA IF NOT EXISTS SILVER;
CREATE SCHEMA IF NOT EXISTS GOLD;
CREATE SCHEMA IF NOT EXISTS dbt_schema;

-- 4. Grant privileges to your user role
GRANT ALL PRIVILEGES ON DATABASE AIRBNB TO ROLE ACCOUNTADMIN;
GRANT ALL PRIVILEGES ON ALL SCHEMAS IN DATABASE AIRBNB TO ROLE ACCOUNTADMIN;
GRANT USAGE ON WAREHOUSE COMPUTE_WHS TO ROLE ACCOUNTADMIN;
```
* **Explanation**: Pre-creates the isolated schemas for each Medallion tier (`STAGING`, `BRONZE`, `SILVER`, `GOLD`) and configures auto-suspension to save compute credits.

---

## 4. Phase 3: Raw Data Ingestion (Staging Layer)

### Step 3.1: Create Staging Tables in Snowflake
Run the table definitions from `DDL/ddl.sql` inside Snowflake:

```sql
USE DATABASE AIRBNB;
USE SCHEMA STAGING;

-- 1. Hosts staging table
CREATE OR REPLACE TABLE HOSTS (
    host_id NUMBER,
    host_name STRING,
    host_since DATE,
    is_superhost BOOLEAN,
    response_rate NUMBER,
    created_at TIMESTAMP,
    PRIMARY KEY (host_id)
);

-- 2. Listings staging table
CREATE OR REPLACE TABLE LISTINGS (
    listing_id NUMBER,
    host_id NUMBER,
    property_type STRING,
    room_type STRING,
    city STRING,
    country STRING,
    accommodates NUMBER,
    bedrooms NUMBER,
    bathrooms NUMBER,
    price_per_night NUMBER,
    created_at TIMESTAMP,
    PRIMARY KEY (listing_id)
);

-- 3. Bookings staging table
CREATE OR REPLACE TABLE BOOKINGS (
    booking_id STRING,
    listing_id NUMBER,
    booking_date TIMESTAMP,
    nights_booked NUMBER,
    booking_amount NUMBER,
    cleaning_fee NUMBER,
    service_fee NUMBER,
    booking_status STRING,
    created_at TIMESTAMP,
    PRIMARY KEY (booking_id)
);
```

### Step 3.2: Load CSVs into Snowflake Staging

Choose **Option A (Snowflake Web UI)** or **Option B (S3 Stage / SnowSQL)**:

#### Option A: Quick Upload via Snowflake Web UI (Snowsight)
1. Go to **Databases** → `AIRBNB` → `STAGING` → **Tables**.
2. Click on `HOSTS` → Click **Load Data** (top right) → Select `SourceData/hosts.csv` → Select CSV Format (Skip Header: 1) → Click **Load**.
3. Repeat the same for `LISTINGS` (`SourceData/listings.csv`) and `BOOKINGS` (`SourceData/bookings.csv`).

#### Option B: AWS S3 External Stage (`DDL/resources.sql`)
```sql
USE DATABASE AIRBNB;
USE SCHEMA STAGING;

CREATE OR REPLACE FILE FORMAT csv_format
  TYPE = 'CSV' 
  FIELD_DELIMITER = ','
  SKIP_HEADER = 1
  ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE;

CREATE OR REPLACE STAGE snowstage
  FILE_FORMAT = csv_format
  URL='s3://your-airbnb-bucket-path/';

COPY INTO HOSTS FROM @snowstage FILES=('hosts.csv') CREDENTIALS=(aws_key_id='...', aws_secret_key='...');
COPY INTO LISTINGS FROM @snowstage FILES=('listings.csv') CREDENTIALS=(aws_key_id='...', aws_secret_key='...');
COPY INTO BOOKINGS FROM @snowstage FILES=('bookings.csv') CREDENTIALS=(aws_key_id='...', aws_secret_key='...');
```

### Step 3.3: Verify Staging Data Counts
```sql
SELECT 'HOSTS' AS tbl, COUNT(*) AS cnt FROM AIRBNB.STAGING.HOSTS
UNION ALL
SELECT 'LISTINGS', COUNT(*) FROM AIRBNB.STAGING.LISTINGS
UNION ALL
SELECT 'BOOKINGS', COUNT(*) FROM AIRBNB.STAGING.BOOKINGS;
```

---

## 5. Phase 4: dbt Profile Configuration & Connection Test

### Step 4.1: Configure `~/.dbt/profiles.yml`
Ensure your local `~/.dbt/profiles.yml` file has the connection configured:

```yaml
aws_dbt_snowflake_project:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: EVLSUJX-WT64945
      user: PLCHANDUGCP48
      password: "{{ env_var('SF_PWD') }}"
      role: ACCOUNTADMIN
      database: AIRBNB
      warehouse: COMPUTE_WHS
      schema: dbt_schema
      threads: 4
      client_session_keep_alive: False
```

### Step 4.2: Test the dbt Connection
Run from the `aws_dbt_snowflake_project` directory:

```bash
cd aws_dbt_snowflake_project
export SF_PWD="your_password"
dbt debug
```
* **Command Breakdown:**
  * `dbt debug`: Validates your `dbt_project.yml`, verifies `profiles.yml` parsing, checks database access, and confirms warehouse permissions.
  * **Expected Output:** All checks end with `OK connection ok`.

### Step 4.3: Install dbt Dependencies
```bash
dbt deps
```
* **Explanation**: Installs any external dbt packages declared in `packages.yml` (if added).

---

## 6. Phase 5: Step-by-Step dbt Transformation Execution

Navigate into `aws_dbt_snowflake_project` for all dbt commands:
```bash
cd /Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project
```

---

### 5.1 Bronze Layer (Raw Ingestion)
The Bronze layer ingests raw data from `AIRBNB.STAGING` with type-casting and incremental support.

```bash
dbt run --select bronze.*
```
* **What this does:**
  * Executes [bronze_bookings.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/models/bronze/bronze_bookings.sql) → creates `AIRBNB.BRONZE.BRONZE_BOOKINGS`
  * Executes [bronze_hosts.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/models/bronze/bronze_hosts.sql) → creates `AIRBNB.BRONZE.BRONZE_HOSTS`
  * Executes [bronze_listings.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/models/bronze/bronze_listings.sql) → creates `AIRBNB.BRONZE.BRONZE_LISTINGS`
* **Under the Hood:**
  * Uses incremental filters: `WHERE CREATED_AT > (SELECT COALESCE(MAX(CREATED_AT), '1900-01-01') FROM {{ this }})` so future runs only process new records.

---

### 5.2 Silver Layer (Transformation & Enrichment)
The Silver layer cleans raw records, applies macros (e.g. `tag()` for price classification), and standardizes column structures.

```bash
dbt run --select silver.*
```
* **What this does:**
  * Executes [silver_bookings.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/models/silver/silver_bookings.sql) → creates `AIRBNB.SILVER.SILVER_BOOKINGS` (calculates totals, validates date ranges)
  * Executes [silver_hosts.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/models/silver/silver_hosts.sql) → creates `AIRBNB.SILVER.SILVER_HOSTS` (cleans response rates, trims host names)
  * Executes [silver_listings.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/models/silver/silver_listings.sql) → creates `AIRBNB.SILVER.SILVER_LISTINGS` (applies `{{ tag(...) }}` macro for low/medium/high pricing tags)

---

### 5.3 Gold Layer (OBT & Fact Models)
The Gold layer prepares business-ready datasets for reporting and dimensional modeling.

```bash
dbt run --select gold.*
```
* **What this does:**
  * Processes intermediate ephemeral models: `bookings.sql`, `hosts.sql`, `listings.sql` (in-memory CTEs without persisting extra tables).
  * Executes [fact.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/models/gold/fact.sql) → creates `AIRBNB.GOLD.FACT` (star schema fact table joining bookings to dimension keys).
  * Executes [obt.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/models/gold/obt.sql) → creates `AIRBNB.GOLD.OBT` (One Big Table combining hosts, listings, and bookings for instant BI dashboarding).

---

### 5.4 Snapshots (SCD Type 2 Dimension Tracking)
Captures historical changes over time (Slowly Changing Dimensions Type 2) using timestamps.

```bash
dbt snapshot
```
* **What this does:**
  * Executes [dim_hosts.yml](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/snapshots/dim_hosts.yml) → `AIRBNB.GOLD.DIM_HOSTS`
  * Executes [dim_listings.yml](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/snapshots/dim_listings.yml) → `AIRBNB.GOLD.DIM_LISTINGS`
  * Executes [dim_bookings.yml](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/snapshots/dim_bookings.yml) → `AIRBNB.GOLD.DIM_BOOKINGS`
* **Result:** Automatically adds `DBT_VALID_FROM`, `DBT_VALID_TO`, and `DBT_SCD_ID` columns to track row mutations.

---

## 7. Phase 6: Data Quality Testing & Governance

Run tests to guarantee uniqueness, null checks, and referential integrity:

```bash
# Run all tests across the project
dbt test

# Run tests for specific layer
dbt test --select bronze.*
dbt test --select silver.*
dbt test --select gold.*
```
* **What this validates:**
  * Checks primary keys for uniqueness and `NOT NULL` constraints.
  * Runs custom data validation tests defined in [source_tests.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/aws_dbt_snowflake_project/tests/source_tests.sql).

---

## 8. Phase 7: Lineage & Documentation Generation

Generate interactive documentation with full lineage graph visualization:

```bash
# 1. Compile project & generate catalog JSONs
dbt docs generate

# 2. Start local documentation web server
dbt docs serve --port 8080
```
* **What this provides:**
  * Interactive schema documentation for all columns and descriptions.
  * Dynamic Medallion **Lineage Graph** visualizing dependencies from `STAGING` → `BRONZE` → `SILVER` → `GOLD` → `SNAPSHOTS`.

---

## 9. Phase 8: One-Shot Build & Maintenance Commands

### The Ultimate One-Shot Build Command:
```bash
dbt build
```
* **Explanation:** `dbt build` executes in optimal dependency order: runs models, executes snapshots, and triggers all tests in a single unified run.

### Full Refresh (Rebuilding Incremental Models from Scratch):
```bash
dbt run --full-refresh
```
* **Explanation:** Drops existing tables and re-executes all incremental models from the beginning of time.

### Clean Project Cache & Artifacts:
```bash
dbt clean
```
* **Explanation:** Deletes compiled artifacts inside `target/` and `dbt_packages/`.

---

## 10. Troubleshooting & FAQs

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`Incorrect username or password`** | Wrong credentials or unescaped characters in password. | Verify username `PLCHANDUGCP48`, wrap password in single quotes `'...'` in `.env` or terminal. |
| **`Object does not exist: STAGING.BOOKINGS`** | Tables not created in Snowflake or wrong active database. | Run [DDL/ddl.sql](file:///Users/chandu/Documents/DBT/SF/Airbnb_Snowflake_DBT_Data_Engineer_Project/DDL/ddl.sql) in Snowflake before executing dbt. |
| **`Warehouse COMPUTE_WHS does not exist`** | Warehouse name typo or user lacks `USAGE` privilege. | Run `CREATE WAREHOUSE COMPUTE_WHS...` and `GRANT USAGE ON WAREHOUSE COMPUTE_WHS TO ROLE ACCOUNTADMIN;`. |
| **`Source not found: staging.listings`** | `AIRBNB.STAGING` schema missing in Snowflake. | Verify `sources.yml` matches database `AIRBNB` and schema `staging`. |
| **`dbt run succeeds but no new data loaded`** | Incremental filter `MAX(created_at)` prevents duplicate loads. | Run `dbt run --full-refresh` to force complete ingestion. |
