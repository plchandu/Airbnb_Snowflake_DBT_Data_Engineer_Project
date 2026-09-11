# Snowflake & dbt Setup Guide

This guide covers step-by-step instructions to configure your Snowflake environment and connect your dbt project (`aws_dbt_snowflake_project`) using the `dev` profile.

---

## 1. Snowflake Prerequisites & Account Setup

Run the following SQL in Snowflake worksheets (logged in as `ACCOUNTADMIN` or a role with appropriate privileges):

```sql
-- 1. Create Virtual Warehouse (if not already existing)
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
  WITH WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 300
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- 2. Create Database
CREATE DATABASE IF NOT EXISTS AIRBNB;

-- 3. Create Default Schema for dbt
USE DATABASE AIRBNB;
CREATE SCHEMA IF NOT EXISTS dbt_schema;

-- 4. Verify User & Role Permissions
-- (Assuming user PLCHANDUGCP48 is already created)
GRANT ROLE ACCOUNTADMIN TO USER PLCHANDUGCP48;
GRANT USAGE ON WAREHOUSE COMPUTE_WHS TO ROLE ACCOUNTADMIN;
GRANT ALL PRIVILEGES ON DATABASE AIRBNB TO ROLE ACCOUNTADMIN;
GRANT ALL PRIVILEGES ON SCHEMA AIRBNB.dbt_schema TO ROLE ACCOUNTADMIN;
```

---

## 2. Locate Your Snowflake Account Identifier

Your Snowflake account locator format is required for the `account` property in `profiles.yml`:

- **Format**: `<orgname>-<accountname>` or `<account_locator>.<region>.<cloud>`
- **Example**: `xy12345.ap-south-2.aws` or `myorg-account1`

To find it directly in Snowflake, execute:
```sql
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS account_identifier;
-- OR
SELECT CURRENT_ACCOUNT();
```

---

## 3. Configure `~/.dbt/profiles.yml`

dbt expects the connection profile in your home directory at `~/.dbt/profiles.yml`.

### Path:
- **macOS / Linux**: `~/.dbt/profiles.yml` (i.e. `/Users/<your-user>/.dbt/profiles.yml`)
- **Windows**: `%USERPROFILE%\.dbt\profiles.yml`

### File Content:

```yaml
aws_dbt_snowflake_project:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: <your_account_identifier>  # e.g., xy12345.ap-south-2.aws or org-account
      user: ANSHLAMBA
      password: <your_snowflake_password>
      role: ACCOUNTADMIN
      database: AIRBNB
      warehouse: COMPUTE_WH
      schema: dbt_schema
      threads: 1
      client_session_keep_alive: False
```

> **Security Tip (Best Practice):** You can store credentials in environment variables instead of plain text:
> ```yaml
> password: "{{ env_var('DBT_SNOWFLAKE_PASSWORD') }}"
> ```

---

## 4. Test dbt Connection

Navigate to your dbt project folder and test your connection:

```bash
cd aws_dbt_snowflake_project
dbt debug
```

If all checks pass with green `OK`, your Snowflake and dbt setup is complete.

---

## 5. Run and Build Models

```bash
# Install package dependencies if any
dbt deps

# Run models (Bronze, Silver, Gold layers)
dbt run

# Run tests
dbt test
```
