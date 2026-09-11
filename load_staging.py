import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

sf_password = os.getenv("SF_PWD")
aws_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

if not sf_password:
    print("❌ ERROR: SF_PWD is missing in .env")
    exit(1)

if not aws_key_id or not aws_secret_key:
    print("❌ ERROR: AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY is missing in .env")
    exit(1)

try:
    print("🔌 Connecting to Snowflake...")
    conn = snowflake.connector.connect(
        user="PLCHANDUGCP48",
        password=sf_password,
        account="EVLSUJX-WT64945",
        warehouse="COMPUTE_WHS",
        database="AIRBNB",
        schema="STAGING",
        role="ACCOUNTADMIN"
    )
    cur = conn.cursor()
    print("✅ Connected successfully!")

    # 1. Ensure File Format exists
    print("\n📄 Step 1: Creating CSV File Format...")
    cur.execute("""
    CREATE OR REPLACE FILE FORMAT csv_format
      TYPE = 'CSV' 
      FIELD_DELIMITER = ','
      SKIP_HEADER = 1
      ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE;
    """)
    print("✅ File format 'csv_format' ready.")

    # 2. Create External Stage pointing to S3
    print("\n☁️ Step 2: Creating External S3 Stage...")
    stage_sql = f"""
    CREATE OR REPLACE STAGE snowstage
      FILE_FORMAT = csv_format
      URL = 's3://airbnb-dbt-snowflake-975829620793/source/'
      CREDENTIALS = (AWS_KEY_ID = '{aws_key_id}', AWS_SECRET_KEY = '{aws_secret_key}');
    """
    cur.execute(stage_sql)
    print("✅ Stage 'snowstage' created.")

    # 3. Copy into HOSTS
    print("\n📥 Step 3: Loading HOSTS table from S3...")
    cur.execute("COPY INTO AIRBNB.STAGING.HOSTS FROM @snowstage FILES = ('hosts.csv');")
    hosts_res = cur.fetchall()
    print(f"✅ HOSTS loaded: {hosts_res[0][0]} -> Status: {hosts_res[0][1]}, Rows parsed: {hosts_res[0][2]}, Loaded: {hosts_res[0][3]}")

    # 4. Copy into LISTINGS
    print("\n📥 Step 4: Loading LISTINGS table from S3...")
    cur.execute("COPY INTO AIRBNB.STAGING.LISTINGS FROM @snowstage FILES = ('listings.csv');")
    listings_res = cur.fetchall()
    print(f"✅ LISTINGS loaded: {listings_res[0][0]} -> Status: {listings_res[0][1]}, Rows parsed: {listings_res[0][2]}, Loaded: {listings_res[0][3]}")

    # 5. Copy into BOOKINGS
    print("\n📥 Step 5: Loading BOOKINGS table from S3...")
    cur.execute("COPY INTO AIRBNB.STAGING.BOOKINGS FROM @snowstage FILES = ('bookings.csv');")
    bookings_res = cur.fetchall()
    print(f"✅ BOOKINGS loaded: {bookings_res[0][0]} -> Status: {bookings_res[0][1]}, Rows parsed: {bookings_res[0][2]}, Loaded: {bookings_res[0][3]}")

    # 6. Summary Row Counts
    print("\n========================================")
    print("📊 STAGING DATA LOAD VERIFICATION:")
    print("========================================")
    cur.execute("""
    SELECT 'HOSTS' AS TABLE_NAME, COUNT(*) AS TOTAL_ROWS FROM AIRBNB.STAGING.HOSTS
    UNION ALL
    SELECT 'LISTINGS', COUNT(*) FROM AIRBNB.STAGING.LISTINGS
    UNION ALL
    SELECT 'BOOKINGS', COUNT(*) FROM AIRBNB.STAGING.BOOKINGS;
    """)
    for row in cur.fetchall():
        print(f"  • Table {row[0]:<10}: {row[1]:>6} rows")
    print("========================================")

    cur.close()
    conn.close()
    print("\n🎉 Ingestion completed successfully!")

except Exception as e:
    print(f"\n❌ Error during ingestion: {e}")
