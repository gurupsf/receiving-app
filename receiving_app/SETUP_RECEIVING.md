# Quick Setup Guide for Receiving App

## Prerequisites
✅ Virtual environment is activated  
✅ Database connection is configured in `.env`

## Setup Steps

### Step 1: Create Database Schema
```bash
# Connect to SQL Server and run the schema script
sqlcmd -S YOUR_SERVER -U YOUR_USER -P YOUR_PASSWORD -d CNtempGuru -i receiving_schema.sql

# Or use SQL Server Management Studio to execute receiving_schema.sql
```

This will create:
- `Receiving_Submissions` table
- `vw_Supplier_KPIs` view
- Necessary indexes

### Step 2: Verify Backend Code
All backend code should be present in:
- ✅ `backend/db.py` - Receiving database functions
- ✅ `backend/main.py` - Receiving API routes
- ✅ `backend/pdf_generator.py` - Receiving PDF generator

### Step 3: Verify Frontend Files
New HTML files created:
- ✅ `frontend/receiving.html` - Receiving form
- ✅ `frontend/receiving_data.html` - Data viewer
- ✅ `frontend/supplier_dashboard.html` - KPI dashboard

### Step 4: Test the Application
```bash
# Start the server (if not already running)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Or with local HTTPS
./run_with_ssl.sh
```

### Step 5: Access the New Features

1. **Receiving Form**:  
   http://YOUR_IP:8000/receiving

2. **Receiving Data**:  
   http://YOUR_IP:8000/receiving-data

3. **Supplier Dashboard**:  
   http://YOUR_IP:8000/supplier-dashboard

## Test Workflow

### Test Case 1: Submit a Receiving Record
1. Go to `/receiving`
2. Select Project and Drawing
3. Enter:
   - PO Number: "PO-2024-001"
   - Material ID: "MAT-12345"
   - Supplier: "Acme Corp"
   - Quantity Ordered: 100
   - Quantity Received: 98
   - Defective Count: 2
   - Order Date: (select a past date)
4. Select "Accepted" status
5. Upload a packing slip photo
6. Upload 1-3 item photos
7. Click Submit
8. ✅ Success message should appear with Receiving ID

### Test Case 2: View Data
1. Go to `/receiving-data`
2. ✅ You should see your submission in the table
3. ✅ Defect rate should show 2.04% (2/98)
4. ✅ Delivery days should be calculated
5. Try filtering by Project or Supplier
6. ✅ Filters should work correctly

### Test Case 3: Check Supplier Dashboard
1. Go to `/supplier-dashboard`
2. ✅ Should see summary cards with metrics
3. ✅ Bar charts should display:
   - Average Delivery Days
   - Defect Rate %
   - Total Orders
4. ✅ Detailed table should show supplier statistics

### Test Case 4: Add Multiple Suppliers
1. Submit 2-3 more receiving records with different suppliers:
   - "Beta Supplies" (no defects, fast delivery)
   - "Gamma Industries" (high defects, slow delivery)
   - "Delta Materials" (medium performance)
2. Go to supplier dashboard
3. ✅ Charts should compare all suppliers visually
4. ✅ Color coding should work (green/orange/red)

## Troubleshooting

### Issue: Database connection error
**Solution**: Check that `WRITE_SQLSERVER_*` variables in `.env` are correct

### Issue: Charts not displaying
**Solution**: Check browser console for errors. Ensure internet connection for Chart.js CDN

### Issue: Images not uploading
**Solution**: 
- Check file size (< 10MB)
- Check file format (PNG, JPG, JPEG only)
- Check browser console for errors

### Issue: PDF not generating
**Solution**:
- Check `PDF_STORAGE_DIR` permissions
- Check `fastapi.log` for detailed errors
- Verify ReportLab and Pillow are installed

### Issue: Delivery days showing as NULL
**Solution**: 
- Order date must be provided in the form
- Check that SQL Server computed column is working

### Issue: Supplier dashboard empty
**Solution**:
- Submit at least one receiving record first
- Ensure supplier name is filled in the form
- Check that the view `vw_Supplier_KPIs` was created successfully

## Validation Checklist

After setup, verify:
- [ ] Database table `Receiving_Submissions` exists
- [ ] Database view `vw_Supplier_KPIs` exists
- [ ] Can access `/receiving` page
- [ ] Can access `/receiving-data` page
- [ ] Can access `/supplier-dashboard` page
- [ ] Can submit a receiving form successfully
- [ ] PDF is generated in correct folder
- [ ] Data appears in receiving data table
- [ ] Supplier dashboard shows metrics
- [ ] Charts render correctly
- [ ] Delete functionality works
- [ ] Filters work correctly

## Navigation

Navigation flow:
```
Receiving Form ←→ Receiving Data ←→ Supplier Dashboard
```

All pages include navigation links in the header for easy switching.

## Next Steps

After successful setup:
1. Train receiving team on the form
2. Establish workflow for order date tracking
3. Set up regular supplier performance reviews
4. Configure automatic alerts for poor performers (future enhancement)
5. Integrate with purchasing system for order dates (future enhancement)

## Support

Check logs:
```bash
tail -f fastapi.log
```

Test API directly:
```bash
# Test supplier KPIs endpoint
curl http://localhost:8000/api/supplier-kpis

# Test receiving submissions endpoint
curl http://localhost:8000/api/receiving-submissions
```
