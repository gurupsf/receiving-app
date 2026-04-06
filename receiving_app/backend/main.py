import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
import json
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import text
from .pdf_generator import generate_qa_pdf, generate_receiving_pdf
import logging
import ssl
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, List


from .db import (
    get_read_engine, get_write_engine,
    fetch_projects, fetch_drawings, get_submissions_table,
    insert_qa_submission, fetch_all_qa_submissions, delete_qa_submission,
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

app = FastAPI(title="QA Form", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Engines
read_engine = get_read_engine()
write_engine = get_write_engine()

# Serve the frontend from ../frontend (kept inside backend/frontend for simplicity)
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class QASubmission(BaseModel):
    project: str
    drawing: str
    elevation: str
    roomNumber: str
    Description: Optional[str] = None
    qaCheck: str  # "Pass" or "Fail"
    issueCategory: str | None = None  # Required if qaCheck is "Fail"
    resubmit: bool = False

    @field_validator("project", "drawing", "elevation", "roomNumber","Description", "qaCheck")
    @classmethod
    def non_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("must not be empty")
        return v

    @field_validator("qaCheck")
    @classmethod
    def valid_qa_check(cls, v):
        if v not in ("Pass", "Fail"):
            raise ValueError("qaCheck must be 'Pass' or 'Fail'")
        return v



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


@app.post("/api/qa-submissions")
async def api_qa_submit(
    project: str = Form(...),
    drawing: str = Form(...),
    elevation: str = Form(...),
    roomNumber: str = Form(...),
    Description: str = Form(None),
    qaCheck: str = Form(...),
    issueCategory: str | None = Form(None),
    resubmit: bool = Form(False),
    files: List[UploadFile] = File(default=[])
):
    """
    Submit a QA form with optional images.
    Expects form data with file uploads.
    """
    try:
        logger.info(f"Received QA submission: project={project}, drawing={drawing}, elevation={elevation}, roomNumber={roomNumber}, qaCheck={qaCheck}")
        
        # Validate required fields
        if not project or not project.strip():
            raise ValueError("Project is required")
        if not drawing or not drawing.strip():
            raise ValueError("Drawing is required")
        if not elevation or not elevation.strip():
            raise ValueError("Elevation is required")
        if not roomNumber or not roomNumber.strip():
            raise ValueError("Room Number is required")
        
        # Validate QA check
        if qaCheck not in ("Pass", "Fail"):
            raise ValueError("qaCheck must be 'Pass' or 'Fail'")
        
        # If Fail, issueCategory is required
        if qaCheck == "Fail" and not issueCategory:
            raise ValueError("issueCategory is required when QA check is 'Fail'")
        
        # Prepare payload for database insertion
        payload = {
            "project": project,
            "drawing": drawing,
            "elevation": elevation,
            "roomNumber": roomNumber,
            "qaCheck": qaCheck,
            "issueCategory": issueCategory,
            "Description": Description,
            "resubmit": resubmit
        }
        
        # Insert into database
        qa_table = "[dbo].[QA_Submissions]"
        qa_id = insert_qa_submission(write_engine, qa_table, payload)
        logger.info(f"QA submission inserted with ID: {qa_id}")
        
        # Process images in-memory for PDF embedding
        image_data = []
        if files:
            for file in files:
                if file.filename:
                    image_bytes = await file.read()
                    image_data.append({"filename": file.filename, "data": image_bytes})
                    logger.info(f"Image processed for PDF: {file.filename}")
        
        # Generate PDF with all form data and images
        pdf_dir = Path(os.getenv("PDF_STORAGE_DIR", "./pdfs")).resolve() / f"project_{project}" / f"drawing_{drawing}"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        tz_ny = ZoneInfo("America/New_York")
        
        qa_data = {
            "qa_id": qa_id,
            "project": project,
            "drawing": drawing,
            "elevation": elevation,
            "roomNumber": roomNumber,
            "Description": Description,
            "qaCheck": qaCheck,
            "issueCategory": issueCategory,
            "resubmit": resubmit,
            "timestamp": datetime.now(tz_ny),
            "image_data": image_data
        }
        
        pdf_path = generate_qa_pdf(qa_data, pdf_dir)
        logger.info(f"QA PDF generated: {pdf_path}")
        
        return {
            "ok": True,
            "qa_id": qa_id,
            "pdf_path": str(pdf_path),
            "images_count": len(image_data)
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"QA submission failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
        logger.error(f"QA submission failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/qasubmissions")
async def api_submit(payload: QASubmission):
    try:
        logger.info(f"Received submission request: {payload}")
        record = payload.model_dump()
        if record.get("projectName"):
            record["projectId"] = record["projectName"].strip() +"@" + datetime.now().strftime("%H:%M:%S")
        record["timestamp"] = pd.Timestamp.utcnow().isoformat()

        # Save to database and get the actual CreatedUtc timestamp
        table = get_submissions_table()
        created_utc = insert_submission(write_engine, table, record)
        
        # Update record with the actual database CreatedUtc for QR generation
        if created_utc:
            record["created_utc"] = created_utc
            logger.info(f"Database insert successful. CreatedUtc: {created_utc}")
        
        response = {"ok": True}
        
        # Generate PDF label if requested
        if payload.generateLabel:
            logger.info("Starting PDF generation")
            pdf_dir = Path(os.getenv("PDF_STORAGE_DIR", "./pdfs")).resolve()
            
            if not pdf_dir.exists():
                logger.debug(f"Creating PDF directory: {pdf_dir}")
                pdf_dir.mkdir(parents=True, exist_ok=True)
            
            # Ensure directory is writable
            if not os.access(pdf_dir, os.W_OK):
                raise PermissionError(f"No write permission for directory: {pdf_dir}")
                
            pdf_path = generate_submission_pdf(record, pdf_dir)
            logger.info(f"PDF generated successfully at: {pdf_path}")
            # Include project_id in the PDF URL for the new structure
            project_id = record.get('projectId')
            response["pdf"] = pdf_path.name
            response["pdf_url"] = f"/pdfs/{project_id}/{pdf_path.name}" if project_id else f"/pdfs/{pdf_path.name}"

            
        return response
    
    
    except Exception as e:
        logger.error(f"Submission failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(e)}
        )

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
# Route handlers for different forms
@app.get("/")
async def root():
    return RedirectResponse(url="/qa")

@app.get("/qa")
async def qa_form():
    """Serve the QA submission form"""
    return FileResponse(FRONTEND_DIR / "qa.html")

@app.get("/api/qa-submissions")
def api_get_qa_submissions(
    projectId: Optional[str] = Query(None, description="Filter by project ID"),
    drawing: Optional[str] = Query(None, description="Filter by drawing name")
):
    try:
        logger.info(f"Fetching QA submissions with filters - projectId: {projectId}, drawing: {drawing}")
        submissions = fetch_all_qa_submissions(project_id=projectId, drawing=drawing)
        logger.info(f"Successfully fetched {len(submissions)} submissions")
        return submissions
    except Exception as e:
        logger.error(f"Failed to fetch QA submissions: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to fetch QA submissions: {str(e)}")

@app.delete("/api/qa-submissions/{qa_id}")
def api_delete_qa_submission(qa_id: int):
    try:
        logger.info(f"Deleting QA submission ID: {qa_id}")
        result = delete_qa_submission(write_engine, qa_id)
        
        if not result:
            raise HTTPException(404, "QA submission not found")
        
        # Delete associated PDF files
        pdf_dir = Path(os.getenv("PDF_STORAGE_DIR", "./pdfs")).resolve()
        project = result["project"]
        drawing = result["drawing"]
        project_dir = pdf_dir / f"project_{project}"
        project_drawing_dir = project_dir / f"drawing_{drawing}"
        
        try:
            if project_drawing_dir.exists():
                # Delete the drawing directory
                import shutil
                shutil.rmtree(project_drawing_dir)
                logger.info(f"Deleted PDF directory: {project_drawing_dir}")
            
            # Check if project directory is now empty and delete it too
            if project_dir.exists() and not any(project_dir.iterdir()):
                project_dir.rmdir()
                logger.info(f"Deleted empty project directory: {project_dir}")
        except Exception as pdf_error:
            logger.warning(f"Failed to delete PDF directory: {pdf_error}")
            # Continue anyway, database deletion succeeded
        
        return {"ok": True, "message": f"QA submission {qa_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete QA submission: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Failed to delete QA submission: {str(e)}")

@app.get("/qa-data")
async def qa_data():
    """Serve the QA data viewing page"""
    return FileResponse(FRONTEND_DIR / "qa_data.html")


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

