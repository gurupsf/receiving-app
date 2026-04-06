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

print(f'\n📊 Database: {database}\n')

odbc_params = f'Driver={{{driver}}};Server={server},{port};Database={database};'
if user and password:
    odbc_params += f'UID={user};PWD={password};'
else:
    odbc_params += 'Trusted_Connection=yes;'
odbc_params += 'Encrypt=no;TrustServerCertificate=yes;'

conn_str = f'mssql+pyodbc:///?odbc_connect={quote_plus(odbc_params)}'
engine = create_engine(conn_str, pool_pre_ping=True)

# Key tables to examine
key_tables = ['PO', 'PO_Item', 'PO_Item_Receive', 'Inventory', 'Part']

print('=' * 80)
print('KEY PURCHASE ORDER TABLES')
print('=' * 80)

with engine.connect() as conn:
    for table in key_tables:
        print(f'\n📋 TABLE: {table}')
        print('-' * 80)
        
        # Check if table exists
        check = conn.execute(text(f"""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = '{table}' AND TABLE_SCHEMA = 'dbo'
        """))
        
        if check.fetchone()[0] == 0:
            print(f'   ⚠️  Table does not exist')
            continue
            
        # Get all columns
        col_result = conn.execute(text(f"""
            SELECT 
                COLUMN_NAME, 
                DATA_TYPE, 
                CHARACTER_MAXIMUM_LENGTH,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = '{table}' AND TABLE_SCHEMA = 'dbo'
            ORDER BY ORDINAL_POSITION
        """))
        
        cols = list(col_result)
        print(f'   Total Columns: {len(cols)}')
        print(f'\n   Column Details:')
        
        for col_name, data_type, max_len, nullable, default in cols:
            null_str = 'NULL' if nullable == 'YES' else 'NOT NULL'
            len_str = f'({max_len})' if max_len else ''
            default_str = f' DEFAULT {default}' if default else ''
            print(f'     • {col_name:40} {data_type}{len_str:20} {null_str}{default_str}')
        
        # Get sample data
        print(f'\n   Sample Data (first 3 rows):')
        try:
            sample = conn.execute(text(f"SELECT TOP 3 * FROM [dbo].[{table}]"))
            rows = sample.fetchall()
            if rows:
                # Get column names
                col_names = [col[0] for col in cols]
                for idx, row in enumerate(rows, 1):
                    print(f'\n     Row {idx}:')
                    for col_idx, col_name in enumerate(col_names[:10]):  # Show first 10 columns
                        try:
                            value = row[col_idx]
                            print(f'       {col_name}: {value}')
                        except:
                            pass
            else:
                print('     (no data)')
        except Exception as e:
            print(f'     Error reading sample: {e}')

print('\n' + '=' * 80)
print('✅ Done!')
print('=' * 80)
