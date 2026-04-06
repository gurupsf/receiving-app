#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

load_dotenv()

driver = os.getenv('ODBC_DRIVER', 'ODBC Driver 17 for SQL Server')
server = os.getenv('METADATA_SQLSERVER_HOST', '')
database = os.getenv('METADATA_SQLSERVER_DATABASE', '')
port = int(os.getenv('METADATA_SQLSERVER_PORT', '1433'))
user = os.getenv('METADATA_SQLSERVER_USER')
password = os.getenv('METADATA_SQLSERVER_PASSWORD')

print(f'\n📊 Connecting to: {server}')
print(f'📊 Database: {database}\n')

odbc_params = f'Driver={{{driver}}};Server={server},{port};Database={database};'
if user and password:
    odbc_params += f'UID={user};PWD={password};'
else:
    odbc_params += 'Trusted_Connection=yes;'
odbc_params += 'Encrypt=no;TrustServerCertificate=yes;'

conn_str = f'mssql+pyodbc:///?odbc_connect={quote_plus(odbc_params)}'
engine = create_engine(conn_str, pool_pre_ping=True)

print('=== 🔍 Searching for PO and Material Tables ===\n')

with engine.connect() as conn:
    # Search for tables with relevant names
    result = conn.execute(text("""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE' 
        AND TABLE_SCHEMA = 'dbo'
        AND (
            TABLE_NAME LIKE '%PO%' OR 
            TABLE_NAME LIKE '%Purchase%' OR 
            TABLE_NAME LIKE '%Order%' OR 
            TABLE_NAME LIKE '%Material%' OR
            TABLE_NAME LIKE '%Item%' OR
            TABLE_NAME LIKE '%Supplier%' OR
            TABLE_NAME LIKE '%Vendor%' OR
            TABLE_NAME LIKE '%Inventory%' OR
            TABLE_NAME LIKE '%Stock%'
        )
        ORDER BY TABLE_NAME
    """))
    
    tables = [row[0] for row in result]
    if tables:
        print(f'✅ Found {len(tables)} potentially relevant tables:\n')
        for table in tables:
            print(f'\n📋 Table: {table}')
            # Get column info for each table
            col_result = conn.execute(text(f"""
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = '{table}' AND TABLE_SCHEMA = 'dbo'
                ORDER BY ORDINAL_POSITION
            """))
            cols = [(row[0], row[1]) for row in col_result]
            print(f'   Total Columns: {len(cols)}')
            print(f'   First 20 columns:')
            for col_name, col_type in cols[:20]:
                print(f'     • {col_name} ({col_type})')
            if len(cols) > 20:
                print(f'     ... and {len(cols) - 20} more columns')
    else:
        print('❌ No tables found with PO/Material/Order keywords')
        print('\n🔍 Showing first 50 tables in database...\n')
        result = conn.execute(text("""
            SELECT TOP 50 TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo'
            ORDER BY TABLE_NAME
        """))
        for row in result:
            print(f'  • {row[0]}')

print('\n✅ Done!')
