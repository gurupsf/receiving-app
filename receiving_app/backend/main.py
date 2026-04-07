import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
from sqlalchemy import text
from .pdf_generator import generate_receiving_pdf
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, List


from .db import (
    get_write_engine,
    fetch_projects, fetch_drawings,
    insert_receiving_submission, fetch_all_receiving_submissions,
    delete_receiving_submission, fetch_supplier_kpis, fetch_suppliers,
    fetch_active_pos, fetch_po_items, search_pos
)

# Configure logging
logging.basicConfig(
    filename='fastapi.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create logger for this module
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="Receiving App", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Engines
write_engine = get_write_engine()

# Serve the frontend from ../frontend (kept inside backend/frontend for simplicity)
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/api/projects")
def api_projects():
    try:
        return fetch_projects()
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch projects: {e}")

@app.get("/api/drawings")
def api_drawings(projectId: str = Query(..., description="Project ID")):
    try:
        return fetch_drawings(projectId)
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch drawings: {e}")


@app.get("/pdfs/{project_id}/{pdf_name}")
async def get_pdf(project_id: str, pdf_name: str):
    pdf_dir = Path(os.getenv("PDF_STORAGE_DIR", "./pdfs")).resolve()
    pdf_path = pdf_dir / f"project_{project_id}" / pdf_name
    if pdf_path.exists():
        return FileResponse(pdf_path, media_type="application/pdf")
    raise HTTPException(404, "PDF not found")



@app.get("/pdfs/{pdf_name}")
async def get_pdf_legacy(pdf_name: str):
    """Legacy endpoint for backward compatibility - searches all project folders"""
    pdf_dir = Path(os.getenv("PDF_STORAGE_DIR", "./pdfs")).resolve()
    

    # First try direct path (old structure)
    pdf_path = pdf_dir / pdf_name
    if pdf_path.exists():
        return FileResponse(pdf_path, media_type="application/pdf")
    

    # Search in project subdirectories
    for project_folder in pdf_dir.glob("project_*"):
        if project_folder.is_dir():
            pdf_path = project_folder / pdf_name
            if pdf_path.exists():
                return FileResponse(pdf_path, media_type="application/pdf")
    

    raise HTTPException(404, "PDF not found")



# --- Frontend routes ---
@app.get("/")
async def root():
    return RedirectResponse(url="/receiving")


# ============================================================================
# RECEIVING APP ROUTES
# ============================================================================

class ReceivingSubmission(BaseModel):
    project: str
    drawing: str
    poNumber: str
    materialId: str
    supplier: Optional[str] = None
    quantityOrdered: int
    quantityReceived: int
    defectiveCount: int = 0
    itemStatus: str  # "Accepted" or "Rejected"
    orderDate: Optional[str] = None  # ISO date string from purchasing
    notes: Optional[str] = None

    @field_validator("project", "drawing", "poNumber", "materialId", "itemStatus")
    @classmethod
    def non_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("must not be empty")
        return v

    @field_validator("itemStatus")
    @classmethod
    def valid_item_status(cls, v):
        if v not in ("Accepted", "Rejected"):
            raise ValueError("itemStatus must be 'Accepted' or 'Rejected'")
        return v

    @field_validator("quantityOrdered", "quantityReceived", "defectiveCount")
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("must be non-negative")
        return v


@app.get("/receiving")
async def receiving_form():
    """Serve the receiving submission form"""
    return FileResponse(FRONTEND_DIR / "receiving.html")


@app.get("/receiving-data")
async def receiving_data():
    """Serve the receiving data viewing page"""
    return FileResponse(FRONTEND_DIR / "receiving_data.html")


@app.get("/supplier-dashboard")
async def supplier_dashboard():
    """Serve the supplier KPI dashboard"""
    return FileResponse(FRONTEND_DIR / "supplier_dashboard.html")


@app.post("/api/receiving-submissions")
async def api_receiving_submit(
    project: str = Form(...),
    drawing: str = Form(...),
    poNumber: str = Form(...),
    materialId: str = Form(...),
    supplier: str = Form(None),
    quantityOrdered: int = Form(...),
    quantityReceived: int = Form(...),
    defectiveCount: int = Form(0),
    itemStatus: str = Form(...),
    orderDate: str = Form(None),  # ISO date string
    notes: str = Form(None),
    poItemId: int = Form(None),  # Link to PO_Item table
    packingSlip: UploadFile = File(None),
    itemPhotos: List[UploadFile] = File(default=[])
):
    """
    Submit a receiving form with optional packing slip and item photos.
    Expects form data with file uploads.
    """
    try:
        logger.info(f"Received receiving submission: PO={poNumber}, Material={materialId}, Supplier={supplier}")
        
        # Validate required fields
        if not project or not project.strip():
            raise ValueError("Project is required")
        if not drawing or not drawing.strip():
            raise ValueError("Drawing is required")
        if not poNumber or not poNumber.strip():
            raise ValueError("PO Number is required")
        if not materialId or not materialId.strip():
            raise ValueError("Material ID is required")
        
        # Validate item status
        if itemStatus not in ("Accepted", "Rejected"):
            raise ValueError("itemStatus must be 'Accepted' or 'Rejected'")
        
        # Validate quantities
        if quantityOrdered < 0 or quantityReceived < 0 or defectiveCount < 0:
            raise ValueError("Quantities must be non-negative")
        
        # Parse order date if provided
        order_date_obj = None
        if orderDate and orderDate.strip():
            try:
                from dateutil import parser
                order_date_obj = parser.parse(orderDate)
            except:
                logger.warning(f"Could not parse order date: {orderDate}")
        
        # Prepare payload for database insertion
        payload = {
            "project": project,
            "drawing": drawing,
            "po_number": poNumber,
            "material_id": materialId,
            "supplier": supplier,
            "quantity_ordered": quantityOrdered,
            "quantity_received": quantityReceived,
            "defective_count": defectiveCount,
            "item_status": itemStatus,
            "order_date": order_date_obj,
            "po_item_id": poItemId, # Link to PO_Item if providedorder_date_obj,
            "notes": notes
        }
        
        # Insert into database
        receiving_table = "[dbo].[Receiving_Submissions]"
        receiving_id = insert_receiving_submission(write_engine, receiving_table, payload)
        logger.info(f"Receiving submission inserted with ID: {receiving_id}")
        
        # Process packing slip image
        packing_slip_data = None
        if packingSlip and packingSlip.filename:
            slip_bytes = await packingSlip.read()
            packing_slip_data = {"filename": packingSlip.filename, "data": slip_bytes}
            logger.info(f"Packing slip processed: {packingSlip.filename}")
        
        # Process item photos
        item_images_data = []
        if itemPhotos:
            for photo in itemPhotos:
                if photo.filename:
                    photo_bytes = await photo.read()
                    item_images_data.append({"filename": photo.filename, "data": photo_bytes})
                    logger.info(f"Item photo processed: {photo.filename}")
        
        # Generate PDF with all form data and images
        pdf_dir = Path(os.getenv("PDF_STORAGE_DIR", "./pdfs")).resolve() / f"project_{project}" / f"po_{poNumber}"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        tz_ny = ZoneInfo("America/New_York")
        
        # Fetch the complete record with computed delivery_days
        from sqlalchemy import text
        with write_engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM [dbo].[Receiving_Submissions] WHERE ID = :id"),
                {"id": receiving_id}
            )
            row = result.fetchone()
            delivery_days = row._mapping.get('Delivery_Days') if row else None
        
        receiving_data = {
            "receiving_id": receiving_id,
            "project": project,
            "drawing": drawing,
            "po_number": poNumber,
            "material_id": materialId,
            "supplier": supplier,
            "quantity_ordered": quantityOrdered,
            "quantity_received": quantityReceived,
            "defective_count": defectiveCount,
            "item_status": itemStatus,
            "order_date": order_date_obj,
            "received_date": datetime.now(tz_ny),
            "delivery_days": delivery_days,
            "notes": notes,
            "timestamp": datetime.now(tz_ny),
            "packing_slip_image": packing_slip_data,
            "item_images": item_images_data
        }
        
        pdf_path = generate_receiving_pdf(receiving_data, pdf_dir)
        logger.info(f"Receiving PDF generated: {pdf_path}")
        
        return {
            "ok": True,
            "receiving_id": receiving_id,
            "pdf_path": str(pdf_path),
            "packing_slip": 1 if packing_slip_data else 0,
            "item_photos_count": len(item_images_data)
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Receiving submission failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/receiving-submissions")
def api_get_receiving_submissions(
    projectId: Optional[str] = Query(None, description="Filter by project ID"),
    poNumber: Optional[str] = Query(None, description="Filter by PO number"),
    supplier: Optional[str] = Query(None, description="Filter by supplier")
):
    try:
        logger.info(f"Fetching receiving submissions with filters - projectId: {projectId}, poNumber: {poNumber}, supplier: {supplier}")
        submissions = fetch_all_receiving_submissions(project_id=projectId, po_number=poNumber, supplier=supplier)
        logger.info(f"Successfully fetched {len(submissions)} receiving submissions")
        return submissions
    except Exception as e:
        logger.error(f"Failed to fetch receiving submissions: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to fetch receiving submissions: {str(e)}")


@app.delete("/api/receiving-submissions/{receiving_id}")
def api_delete_receiving_submission(receiving_id: int):
    try:
        logger.info(f"Deleting receiving submission ID: {receiving_id}")
        result = delete_receiving_submission(write_engine, receiving_id)
        
        if not result:
            raise HTTPException(404, "Receiving submission not found")
        
        # Delete associated PDF files
        pdf_dir = Path(os.getenv("PDF_STORAGE_DIR", "./pdfs")).resolve()
        project = result["project"]
        po_number = result["po_number"]
        project_dir = pdf_dir / f"project_{project}"
        po_dir = project_dir / f"po_{po_number}"
        
        try:
            if po_dir.exists():
                import shutil
                shutil.rmtree(po_dir)
                logger.info(f"Deleted PDF directory: {po_dir}")
            
            # Check if project directory is now empty and delete it too
            if project_dir.exists() and not any(project_dir.iterdir()):
                project_dir.rmdir()
                logger.info(f"Deleted empty project directory: {project_dir}")
        except Exception as pdf_error:
            logger.warning(f"Failed to delete PDF directory: {pdf_error}")
        
        return {"ok": True, "message": f"Receiving submission {receiving_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete receiving submission: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to delete receiving submission: {str(e)}")


@app.get("/api/supplier-kpis")
def api_get_supplier_kpis():
    """
    Get KPI data for all suppliers including:
    - Average delivery days
    - Average defective items
    - Defect rate percentage
    - Total orders and quantities
    """
    try:
        logger.info("Fetching supplier KPIs")
        kpis = fetch_supplier_kpis()
        logger.info(f"Successfully fetched KPIs for {len(kpis)} suppliers")
        return kpis
    except Exception as e:
        logger.error(f"Failed to fetch supplier KPIs: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to fetch supplier KPIs: {str(e)}")


@app.get("/api/suppliers")
def api_get_suppliers():
    """Get list of all suppliers"""
    try:
        return fetch_suppliers()
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch suppliers: {e}")


# ============================================================================
# PO INTEGRATION ENDPOINTS
# ============================================================================

@app.get("/api/pos")
def api_get_pos(
    projectId: Optional[str] = Query(None, description="Filter by project ID"),
    search: Optional[str] = Query(None, description="Search PO number or vendor")
):
    """Get list of active purchase orders"""
    try:
        if search:
            return search_pos(search)
        else:
            return fetch_active_pos(project_id=projectId)
    except Exception as e:
        logger.error(f"Failed to fetch POs: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to fetch POs: {e}")


@app.get("/api/pos/{po_identifier}/items")
def api_get_po_items(po_identifier: str):
    """
    Get items for a specific PO.
    po_identifier can be either PO ID (numeric) or PO StringID (like 'PO-2024-001')
    """
    try:
        # Check if it's numeric ID or string ID
        if po_identifier.isdigit():
            items = fetch_po_items(po_id=int(po_identifier))
        else:
            items = fetch_po_items(po_string_id=po_identifier)
        
        if not items:
            raise HTTPException(404, f"No items found for PO: {po_identifier}")
        
        return items
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch PO items: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to fetch PO items: {e}")

