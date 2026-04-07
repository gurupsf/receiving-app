# Receiving App - Material Receipt & Supplier Performance Tracking

## Overview
A comprehensive receiving application built with FastAPI for tracking material receipts, managing purchase orders, and monitoring supplier performance with detailed KPIs.

## Features

### 1. Receiving Form (`/receiving`)
- **Project & Drawing Selection**: Dropdown populated from database
- **Purchase Order Tracking**: PO number, material ID, supplier information
- **Quantity Management**: 
  - Quantity Ordered
  - Quantity Received
  - Defective Count (automatic defect rate calculation)
- **Item Status**: Accept/Reject with visual indicators
- **Delivery Time Tracking**:
  - Order Date (from purchasing system)
  - Received Date (automatic timestamp)
  - Calculated delivery days
- **Photo Uploads**:
  - **Packing Slip Photo**: Single photo of the packing slip
  - **Item Photos**: Multiple photos of received items (separate section)
- **PDF Generation**: Comprehensive receiving reports with all data and images

### 2. Receiving Data Viewer (`/receiving-data`)
- View all receiving submissions in a sortable table
- **Filters**:
  - Filter by Project
  - Filter by PO Number
  - Filter by Supplier
- **Display Metrics**:
  - All form data
  - Calculated defect rate percentage
  - Delivery days
  - Color-coded status badges
- Delete functionality with PDF cleanup

### 3. Supplier Dashboard (`/supplier-dashboard`)
Visual analytics dashboard with two main KPIs:

#### KPI #1: Average Delivery Time (ETA)
- Average delivery days per supplier
- Bar chart comparison across all suppliers
- Color-coded metrics:
  - Green: ≤7 days (Good)
  - Orange: 8-14 days (Warning)
  - Red: >14 days (Poor)

#### KPI #2: Average Defective Rate
- Defect rate percentage per supplier
- Bar chart comparison across all suppliers
- Color-coded metrics:
  - Green: ≤5% (Good)
  - Orange: 6-10% (Warning)
  - Red: >10% (Poor)

#### Additional Features:
- Total orders per supplier (bar chart)
- Summary cards with overall metrics
- Detailed table with all supplier statistics
- Accept/Reject counts per supplier
- First and last order dates

## Database Schema

### Table: `Receiving_Submissions`
```sql
- ID (Primary Key, Auto-increment)
- Project (NVARCHAR(100))
- Drawing (NVARCHAR(100))
- PO_Number (NVARCHAR(100))
- Material_ID (NVARCHAR(100))
- Supplier (NVARCHAR(200))
- Quantity_Ordered (INT)
- Quantity_Received (INT)
- Defective_Count (INT)
- Item_Status ('Accepted' or 'Rejected')
- Order_Date (DATETIME2) - from purchasing
- Received_Date (DATETIME2) - auto-set
- Delivery_Days (COMPUTED COLUMN)
- Notes (NVARCHAR(MAX))
- Timestamp (DATETIME2)
```

### View: `vw_Supplier_KPIs`
Aggregates supplier performance metrics:
- Total Orders
- Total Quantity Received
- Total Defective Items
- Average Defective Per Order
- Average Delivery Days
- Defect Rate Percentage
- Accepted/Rejected Counts
- First/Last Order Dates

## Installation & Setup

### 1. Run Database Schema
```bash
# Execute the schema creation script in SQL Server
sqlcmd -S YOUR_SERVER -U YOUR_USER -P YOUR_PASSWORD -d YOUR_DB -i receiving_schema.sql
```

### 2. Configure Environment Variables
Add to your `.env` file:
```env
# Existing QA variables...

# PDF Storage (shared with QA app)
PDF_STORAGE_DIR=./pdfs

# Database connections already configured for QA app work for Receiving too
```

### 3. Dependencies
All required packages are already in `requirements.txt`:
- fastapi
- uvicorn
- sqlalchemy
- pyodbc
- reportlab
- python-multipart
- pillow
- qrcode
- python-dateutil

### 4. Run the Application
```bash
# Activate virtual environment
source /home/guru/receiving_app/env/bin/activate

# Start server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Or with SSL
./run_with_ssl.sh
```

`run_with_ssl.sh` uses `SSL_KEYFILE` and `SSL_CERTFILE` when provided.
If they are not set, it generates a local self-signed certificate in `/tmp/receiving_app_ssl`.

## API Endpoints

### Receiving Endpoints
- `POST /api/receiving-submissions` - Submit receiving form with images
- `GET /api/receiving-submissions` - Fetch all submissions (with filters)
  - Query params: `projectId`, `poNumber`, `supplier`
- `DELETE /api/receiving-submissions/{id}` - Delete submission
- `GET /api/supplier-kpis` - Get supplier performance metrics
- `GET /api/suppliers` - Get list of all suppliers

### Frontend Routes
- `GET /receiving` - Receiving submission form
- `GET /receiving-data` - Data viewer/management
- `GET /supplier-dashboard` - Supplier KPI dashboard

## PDF Generation

PDFs are organized by project and PO number:
```
pdfs/
  project_{project_id}/
    po_{po_number}/
      Receiving_{id}_{po}_{material}.pdf
```

Each PDF contains:
- Complete form data table
- Calculated defect rate
- Delivery time information
- Packing slip photo (full page, separate section)
- Item photos (multiple, each on separate page if needed)

## Navigation

The app includes navigation between:
- Receiving Form (`/receiving`)
- Receiving Data (`/receiving-data`)
- Supplier Dashboard (`/supplier-dashboard`)

## Usage Workflow

1. **Purchasing Orders Material**
   - Record order date in purchasing system
   - Provide PO number to receiving team

2. **Receiving Team Inspects Material**
   - Access receiving form at `/receiving`
   - Select project and drawing
   - Enter PO number and material ID
   - Enter supplier name
   - Input quantities (ordered, received, defective)
   - Take photo of packing slip
   - Take photos of items
   - Mark as Accepted or Rejected
   - Submit form

3. **System Automatically**
   - Calculates defect rate
   - Calculates delivery days (if order date provided)
   - Generates comprehensive PDF report
   - Updates supplier KPIs in real-time

4. **Management Reviews**
   - View individual submissions at `/receiving-data`
   - Monitor supplier performance at `/supplier-dashboard`
   - Compare suppliers using visual charts
   - Identify problematic suppliers (high defect rate, slow delivery)

## Color Coding

### Defect Rate:
- 🟢 Green: ≤5% (Excellent)
- 🟠 Orange: 6-10% (Needs attention)
- 🔴 Red: >10% (Critical)

### Delivery Days:
- 🟢 Green: ≤7 days (Fast)
- 🟠 Orange: 8-14 days (Average)
- 🔴 Red: >14 days (Slow)

## Future Enhancements

Possible additions:
- Email notifications for rejected items
- Automatic supplier ratings
- Trend analysis over time
- Integration with purchasing system for automatic order date import
- Barcode scanning for material IDs
- Mobile-optimized interface
- Export supplier reports to Excel
- Historical comparison charts

## Support

For issues or questions, check:
1. Database connection settings in `.env`
2. SQL Server permissions for views and tables
3. PDF storage directory permissions
4. FastAPI logs at `fastapi.log`

## Architecture

Built with a simple FastAPI + SQL Server stack:
- **Backend**: FastAPI with SQLAlchemy
- **Database**: SQL Server with computed columns and views
- **Frontend**: Vanilla HTML/CSS/JavaScript with Chart.js
- **PDF**: ReportLab with image embedding
- **Photos**: In-memory processing, embedded in PDFs only
