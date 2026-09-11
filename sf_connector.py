import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

password = os.getenv("SF_PWD") or os.getenv("SNOWFLAKE_PASSWORD")

if not password:
    print("❌ ERROR: SF_PWD environment variable or .env entry is not set!")
    exit(1)

try:
    conn = snowflake.connector.connect(
        user="PLCHANDUGCP48",
        password=password,
        account="EVLSUJX-WT64945",
        warehouse="COMPUTE_WHS",
        role="ACCOUNTADMIN"
    )
    cur = conn.cursor()
    print("✅ Connected to Snowflake successfully!")

    # 1. Ensure Database and Schema exist
    cur.execute("CREATE DATABASE IF NOT EXISTS AIRBNB;")
    cur.execute("USE DATABASE AIRBNB;")
    cur.execute("CREATE SCHEMA IF NOT EXISTS STAGING;")
    cur.execute("USE SCHEMA STAGING;")

    # 2. Create the Staging Tables
    print("\n📦 Creating staging tables in AIRBNB.STAGING...")
    cur.execute("""
    CREATE OR REPLACE TABLE HOSTS (
        host_id NUMBER,
        host_name STRING,
        host_since DATE,
        is_superhost BOOLEAN,
        response_rate NUMBER,
        created_at TIMESTAMP,
        PRIMARY KEY (host_id)
    );
    """)

    cur.execute("""
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
    """)

    cur.execute("""
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
    """)

    # 3. Query SHOW TABLES
    print("\n🔍 Querying SHOW TABLES IN AIRBNB.STAGING:")
    cur.execute("SHOW TABLES IN SCHEMA AIRBNB.STAGING;")
    rows = cur.fetchall()
    for row in rows:
        print(f"  • Table: {row[1]} | Schema: {row[4]} | Database: {row[3]} | Kind: {row[5]}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
