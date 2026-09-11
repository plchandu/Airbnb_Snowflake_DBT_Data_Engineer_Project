# AWS & Snowflake: Security and Governance Guide

When integrating Snowflake with AWS in an enterprise Data Engineering environment, security and governance must be implemented across multiple layers. This guide outlines the detailed, step-by-step best practices for securing your data pipeline.

---

## 1. Storage Integration (Secure S3 Ingestion)
Passing AWS Access Keys directly in `COPY INTO` commands is a security risk. In production, you should use **Storage Integrations** combined with AWS IAM Roles.

### Step-by-Step Implementation:
1. **Create an IAM Role in AWS:**
   - Create a new IAM Role.
   - Attach an inline policy that grants `s3:GetObject`, `s3:GetObjectVersion`, and `s3:ListBucket` permissions exclusively to your target S3 bucket.
2. **Create a Storage Integration in Snowflake:**
   ```sql
   CREATE STORAGE INTEGRATION s3_int
     TYPE = EXTERNAL_STAGE
     STORAGE_PROVIDER = 'S3'
     ENABLED = TRUE
     STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/my_s3_snowflake_role'
     STORAGE_ALLOWED_LOCATIONS = ('s3://my-dbt-bucket/raw_data/');
   ```
3. **Establish Trust:**
   - Run `DESC INTEGRATION s3_int;` in Snowflake.
   - Copy the `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID`.
   - Update the Trust Relationship of your AWS IAM Role to allow these specific Snowflake credentials to assume the role.
4. **Create a Secure Stage:**
   ```sql
   CREATE STAGE my_secure_stage
     URL = 's3://my-dbt-bucket/raw_data/'
     STORAGE_INTEGRATION = s3_int;
   ```

---

## 2. Network Security (AWS PrivateLink)
To ensure that your data does not traverse the public internet while moving from AWS to Snowflake, configure **AWS PrivateLink**.

### Step-by-Step Implementation:
1. Contact Snowflake Support (or use `SYSTEM$GET_PRIVATELINK_CONFIG()`) to get your Snowflake VPC account details.
2. In AWS, navigate to VPC Endpoints and create a new endpoint connecting to the Snowflake service.
3. Update your DNS settings in AWS Route53 so that your Snowflake URL (e.g., `account.snowflakecomputing.com`) resolves privately within your VPC.
4. In Snowflake, configure **Network Policies** to block all public IP traffic and only allow traffic originating from your AWS VPC CIDR block.

---

## 3. Data Encryption (Transit & Rest)
Snowflake encrypts data by default, but enterprise governance often requires you to control the encryption keys.

### Step-by-Step Implementation:
1. **AWS S3 Encryption:** Ensure your S3 bucket has default encryption enabled using **AWS KMS** (Key Management Service).
2. **In-Transit Encryption:** Ensure all connections use TLS 1.2+ (Snowflake drivers do this automatically).
3. **Tri-Secret Secure (Snowflake):** 
   - Create a Customer Managed Key (CMK) in AWS KMS.
   - Share this key securely with Snowflake.
   - Snowflake combines your KMS key with its own managed key to encrypt the data at rest. If you disable your KMS key, the data in Snowflake immediately becomes unreadable.

---

## 4. Identity & Access Management (SSO & RBAC)
Avoid managing local user passwords in Snowflake. Rely on an Identity Provider (IdP) for authentication and use strict Role-Based Access Control (RBAC) for authorization.

### Step-by-Step Implementation:
1. **Integrate SSO:** Connect Snowflake to your IdP (e.g., Okta, Microsoft Entra ID, or AWS IAM Identity Center) using SAML 2.0.
2. **Implement RBAC:** Create functional roles rather than granting privileges directly to users.
   ```sql
   CREATE ROLE data_engineer;
   CREATE ROLE bi_analyst;
   ```
3. **Automate Grants with dbt:** In your `dbt_project.yml`, configure dbt to automatically grant read permissions to your BI roles whenever a model is built.
   ```yaml
   models:
     my_project:
       gold:
         +grants:
           select: ['bi_analyst']
   ```

---

## 5. Data Governance (Column-Level Security)
Mask sensitive Personally Identifiable Information (PII) so that only authorized roles can view the raw data, while downstream analysts see masked values.

### Step-by-Step Implementation:
1. **Define a Masking Policy:**
   ```sql
   CREATE OR REPLACE MASKING POLICY hide_pii_string AS (val string) RETURNS string ->
     CASE
       WHEN CURRENT_ROLE() IN ('ACCOUNTADMIN', 'DATA_ENGINEER') THEN val
       ELSE '***MASKED***'
     END;
   ```
2. **Apply via dbt Post-Hooks:** Add the masking policy to your dbt model configurations so it persists across table rebuilds.
   ```jinja
   {{ config(
       post_hook="ALTER TABLE {{ this }} MODIFY COLUMN EMAIL SET MASKING POLICY hide_pii_string;"
   ) }}
   ```

---

## 6. Auditing & Logging
Ensure all data access is tracked for compliance (SOC2, GDPR, HIPAA).

### Step-by-Step Implementation:
1. **AWS CloudTrail:** Enable CloudTrail in AWS to log every time Snowflake assumes the IAM role and reads objects from S3.
2. **Snowflake Access History:** Query Snowflake's built-in `ACCOUNT_USAGE` schemas to audit user activity.
   ```sql
   SELECT user_name, query_text, start_time 
   FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
   WHERE start_time > DATEADD(day, -7, CURRENT_DATE());
   ```
3. **Tagging:** Apply Snowflake Object Tags to sensitive columns (e.g., `TAG PII = 'true'`) to make auditing and reporting easier.
