# Complex Data Security & Governance Implementation (Airbnb Project)

This document outlines an advanced, enterprise-grade Data Security and Governance architecture specifically tailored for this Airbnb dbt + Snowflake project. It moves beyond basic RBAC and implements **Tag-Based Data Masking**, **Row-Level Security**, and **Automated Auditing**.

---

## 1. Role-Based Access Control (RBAC) Hierarchy
A production environment requires strict segregation of duties. We will implement the following role hierarchy:

* **`SECURITYADMIN`**: Manages users, roles, and masking policies. Has no access to read the actual data.
* **`SYSADMIN`**: Manages virtual warehouses and databases.
* **`DATA_ENGINEER_ROLE`**: Can read S3 stages and write to the `BRONZE` and `SILVER` schemas.
* **`DBT_CLOUD_ROLE`**: The service account role used by dbt to run transformations in production. Can read `SILVER` and build `GOLD`.
* **`BI_ANALYST_ROLE`**: Can only read `GOLD` models, subject to Row-Level Security and Column-Level Masking.
* **`DATA_SCIENTIST_ROLE`**: Can read `SILVER` and `GOLD`, subject to Column-Level Masking.

---

## 2. Tag-Based Dynamic Data Masking (Column-Level Security)
Instead of applying a masking policy to every single column manually, we will use **Snowflake Object Tags**. We define the policy on the *tag*, and dbt automatically applies the tag to the columns.

### Step 1: Create the Tag & Policy in Snowflake (by `SECURITYADMIN`)
```sql
USE ROLE SECURITYADMIN;
CREATE TAG AIRBNB.GOLD.PII_SENSITIVITY_LEVEL;

CREATE OR REPLACE MASKING POLICY pii_tag_mask AS (val string) RETURNS string ->
  CASE
    WHEN CURRENT_ROLE() IN ('DATA_ENGINEER_ROLE', 'DBT_CLOUD_ROLE') THEN val
    WHEN SYSTEM$GET_TAG_ON_CURRENT_COLUMN('PII_SENSITIVITY_LEVEL') = 'HIGH' THEN '***REDACTED***'
    WHEN SYSTEM$GET_TAG_ON_CURRENT_COLUMN('PII_SENSITIVITY_LEVEL') = 'LOW' THEN SHA2(val) -- Hashed
    ELSE val
  END;

ALTER TAG AIRBNB.GOLD.PII_SENSITIVITY_LEVEL SET MASKING POLICY pii_tag_mask;
```

### Step 2: Apply via dbt `schema.yml`
Using the `dbt-snowflake-monitoring` or custom macros, we simply tag the columns in our dbt YAML files. Snowflake automatically applies the masking policy.

```yaml
models:
  - name: dim_hosts
    columns:
      - name: host_name
        tags: ["pii"]
        meta:
          snowflake_tags:
            - PII_SENSITIVITY_LEVEL: 'HIGH'
```

---

## 3. Row-Level Security (RLS) for BI Analysts
Airbnb data spans multiple countries. We want to ensure that an analyst in France can only see French listings, while global managers can see everything.

### Step 1: Create an Entitlements Mapping Table
```sql
CREATE TABLE AIRBNB.GOLD.ANALYST_ENTITLEMENTS (
    ROLE_NAME STRING,
    ALLOWED_COUNTRY STRING
);
INSERT INTO AIRBNB.GOLD.ANALYST_ENTITLEMENTS VALUES 
    ('BI_FRANCE_ROLE', 'France'),
    ('BI_US_ROLE', 'United States'),
    ('BI_GLOBAL_ROLE', 'ALL');
```

### Step 2: Create a Row Access Policy
```sql
CREATE OR REPLACE ROW ACCESS POLICY country_policy AS (country_val varchar) RETURNS BOOLEAN ->
  CURRENT_ROLE() IN ('ACCOUNTADMIN', 'DBT_CLOUD_ROLE', 'DATA_ENGINEER_ROLE')
  OR EXISTS (
      SELECT 1 FROM AIRBNB.GOLD.ANALYST_ENTITLEMENTS
      WHERE ROLE_NAME = CURRENT_ROLE() 
      AND (ALLOWED_COUNTRY = country_val OR ALLOWED_COUNTRY = 'ALL')
  );
```

### Step 3: Apply RLS via dbt Post-Hook in `obt.sql`
```jinja
{{ config(
    materialized='table',
    post_hook="ALTER TABLE {{ this }} ADD ROW ACCESS POLICY country_policy ON (COUNTRY);"
) }}
```

---

## 4. Automated Data Quality & Anomaly Detection (Governance)
Governance isn't just about security; it is about trusting the data. We will implement the `dbt-expectations` package for advanced testing.

### Add to `packages.yml`:
```yaml
packages:
  - package: calogica/dbt_expectations
    version: 0.9.0
```

### Add to `models/gold/schema.yml`:
```yaml
models:
  - name: fact
    columns:
      - name: total_amount
        tests:
          - dbt_expectations.expect_column_values_to_be_between:
              min_value: 0
              max_value: 100000  # Alert if an Airbnb booking is over $100k (anomaly)
```

---

## 5. Security Auditing (Automated Compliance Reporting)
To satisfy SOC2/GDPR compliance, we need to prove who accessed what. We will create a new dbt model (`models/governance/security_audit.sql`) that queries Snowflake's metadata to track unauthorized access attempts.

```sql
{{ config(materialized='incremental', schema='governance') }}

SELECT 
    query_id,
    user_name,
    role_name,
    start_time,
    query_text,
    error_message
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE 
    error_code IN ('1003', '3001') -- Access Denied / Object Does Not Exist (Unauthorized)
    AND start_time > (SELECT MAX(start_time) FROM {{ this }})
```
*We then set up a Snowflake Alert to email the Security Team if this model generates new rows.*

---

## Summary of the Complex Implementation:
1. **Network:** Locked to AWS VPC via PrivateLink.
2. **Access:** Strict RBAC hierarchy. Service Accounts run dbt; humans read from BI tools.
3. **Column Security:** Tag-based Dynamic Data Masking.
4. **Row Security:** Entitlements-driven Row Access Policies.
5. **Quality:** `dbt-expectations` for anomaly detection.
6. **Auditing:** Incremental dbt model tracking unauthorized access in `ACCOUNT_USAGE`.
