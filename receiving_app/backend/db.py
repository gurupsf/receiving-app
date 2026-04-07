import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()



# ---------- helpers ----------
def _bool(env_name: str, default: bool = False) -> bool:
    raw = os.getenv(env_name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "y", "on")




def _make_engine(prefix: str) -> Engine:
    driver   = os.getenv("ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    server   = os.getenv(f"{prefix}SQLSERVER_HOST", "")
    database = os.getenv(f"{prefix}SQLSERVER_DATABASE", "")
    port     = int(os.getenv(f"{prefix}SQLSERVER_PORT", "1433"))
    encrypt  = _bool(f"{prefix}SQLSERVER_ENCRYPT", False)
    
    # Check if user/password are provided, if not use Windows Auth
    user     = os.getenv(f"{prefix}SQLSERVER_USER")
    password = os.getenv(f"{prefix}SQLSERVER_PASSWORD")
    
    odbc_params = (
        f"Driver={{{driver}}};"
        f"Server={server},{port};"
        f"Database={database};"
    )
    
    # Add authentication parameters
    if user and password:
        # SQL Server Authentication
        odbc_params += f"UID={user};PWD={password};"
    else:
        # Windows Authentication
        odbc_params += "Trusted_Connection=yes;"
    
    odbc_params += f"Encrypt={'yes' if encrypt else 'no'};"
    odbc_params += f"TrustServerCertificate=yes;"
    
    conn_str = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_params)}"
    engine = create_engine(conn_str, pool_pre_ping=True, pool_size=5, max_overflow=10, future=True)
    return engine

# ---------- engines ----------
_read_engine: Engine | None = None
_write_engine: Engine | None = None
_metadata_engine: Engine | None = None




def get_read_engine() -> Engine:
    global _read_engine
    if _read_engine is None:
        _read_engine = _make_engine("READ_")
    return _read_engine

def get_write_engine() -> Engine:
    global _write_engine
    if _write_engine is None:
        _write_engine = _make_engine("WRITE_")
    return _write_engine




def get_metadata_engine() -> Engine:
    """
    Returns engine for metadata queries (Projects, Drawings, etc.).
    Uses METADATA_ prefix for environment variables.
    """
    global _metadata_engine
    if _metadata_engine is None:
        _metadata_engine = _make_engine("METADATA_")
    return _metadata_engine













# ---------- READ QUERIES ----------
def fetch_projects():
    """
    Returns [{id, name}] for the Projects dropdown.
    Change name to a friendlier column (e.g., P.JobName) if you have it.
    """
    engine = get_metadata_engine()
    sql_stmt = text("""
        SELECT
            CAST(P.ID AS varchar(50)) AS id,
            CAST(P.ID AS varchar(50)) AS name  -- swap to P.JobName if available
        FROM [dbo].[Project] AS P
        WHERE P.ID > 1900
        ORDER BY P.ID
    """)
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(sql_stmt)]

def fetch_drawings(project_id: str):
    """
    Returns drawings/phases for a given project: [{id, name, projectId}].
    """
    engine = get_metadata_engine()
    sql_stmt = text("""
        SELECT
            CAST(PP.ID AS varchar(50)) AS id,
            PP.Description AS name,
            PP.Project     AS projectId
        FROM [dbo].[Project_Phase] AS PP
        JOIN [dbo].[Project] AS P ON PP.Project = P.ID
        WHERE PP.Project = :project_id
        ORDER BY PP.Description
    """)
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(sql_stmt, {"project_id": project_id})]


# ---------- RECEIVING SUBMISSION FUNCTIONS ----------
def insert_receiving_submission(engine: Engine, table_name: str, payload: dict):
    """
    Inserts one receiving submission row into the Receiving_Submissions table.
    Expected keys:
      project, drawing, po_number, material_id, supplier, quantity_ordered,
      quantity_received, defective_count, item_status, order_date, notes, po_item_id
    Returns:
      int: The ID of the inserted record
    """
    sql_stmt = text(f"""
        INSERT INTO {table_name}
        (
            Project,
            Drawing,
            PO_Number,
            Material_ID,
            Supplier,
            Quantity_Ordered,
            Quantity_Received,
            Defective_Count,
            Item_Status,
            Order_Date,
            Received_Date,
            Notes,
            POItem_ID
        )
        OUTPUT INSERTED.ID
        VALUES
        (
            :project,
            :drawing,
            :po_number,
            :material_id,
            :supplier,
            :quantity_ordered,
            :quantity_received,
            :defective_count,
            :item_status,
            :order_date,
            GETUTCDATE(),
            :notes,
            :po_item_id
        );
    """)
    with engine.begin() as conn:
        result = conn.execute(sql_stmt, payload)
        receiving_id = result.fetchone()[0]
        return receiving_id


def fetch_all_receiving_submissions(project_id: str = None, po_number: str = None, supplier: str = None):
    """
    Returns all receiving submissions with optional filtering.
    """
    engine = get_write_engine()
    params = {}
    where_clause = ""
    
    if project_id:
        where_clause += " AND Project = :project_id"
        params["project_id"] = project_id
    
    if po_number:
        where_clause += " AND PO_Number = :po_number"
        params["po_number"] = po_number
    
    if supplier:
        where_clause += " AND Supplier = :supplier"
        params["supplier"] = supplier
    
    sql_stmt = text(f"""
        SELECT
            ID,
            Project,
            Drawing,
            PO_Number,
            Material_ID,
            Supplier,
            Quantity_Ordered,
            Quantity_Received,
            Defective_Count,
            Item_Status,
            Order_Date,
            Received_Date,
            Delivery_Days,
            Notes,
            Timestamp
        FROM [dbo].[Receiving_Submissions]
        WHERE 1=1{where_clause}
        ORDER BY Timestamp DESC
    """)
    
    with engine.connect() as conn:
        rows = conn.execute(sql_stmt, params)
        return [dict(r._mapping) for r in rows]


def fetch_supplier_kpis():
    """
    Returns KPI data for all suppliers using the vw_Supplier_KPIs view.
    """
    engine = get_write_engine()
    sql_stmt = text("""
        SELECT
            Supplier,
            Total_Orders,
            Total_Quantity_Received,
            Total_Defective,
            Avg_Defective_Per_Order,
            Avg_Delivery_Days,
            Defect_Rate_Percent,
            Accepted_Count,
            Rejected_Count,
            First_Order_Date,
            Last_Order_Date
        FROM [dbo].[vw_Supplier_KPIs]
        ORDER BY Supplier
    """)
    
    with engine.connect() as conn:
        rows = conn.execute(sql_stmt)
        return [dict(r._mapping) for r in rows]


def delete_receiving_submission(engine: Engine, receiving_id: int):
    """
    Deletes a receiving submission by ID.
    Returns the submission details for cleanup, or None if not found.
    """
    # First fetch the submission to get project and po info
    fetch_stmt = text("""
        SELECT Project, PO_Number FROM [dbo].[Receiving_Submissions]
        WHERE ID = :receiving_id
    """)
    with engine.connect() as conn:
        result = conn.execute(fetch_stmt, {"receiving_id": receiving_id})
        row = result.fetchone()
        if not row:
            return None
        project, po_number = row[0], row[1]
    
    # Now delete the submission
    delete_stmt = text("""
        DELETE FROM [dbo].[Receiving_Submissions]
        WHERE ID = :receiving_id
    """)
    with engine.begin() as conn:
        result = conn.execute(delete_stmt, {"receiving_id": receiving_id})
        if result.rowcount > 0:
            return {"project": project, "po_number": po_number, "receiving_id": receiving_id}
    
    return None


def fetch_suppliers():
    """
    Returns distinct list of suppliers from receiving submissions.
    """
    engine = get_write_engine()
    sql_stmt = text("""
        SELECT DISTINCT Supplier
        FROM [dbo].[Receiving_Submissions]
        WHERE Supplier IS NOT NULL
        ORDER BY Supplier
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql_stmt)
        return [{"name": row[0]} for row in rows]


# ---------- PO INTEGRATION FUNCTIONS ----------
def fetch_active_pos(project_id: str = None):
    """
    Fetch active purchase orders with items from the PO system.
    Returns POs with vendor and item information.
    """
    engine = get_metadata_engine()
    
    where_clause = ""
    params = {}
    
    if project_id:
        where_clause = " AND PI.Project = :project_id"
        params["project_id"] = project_id
    
    sql_stmt = text(f"""
        SELECT DISTINCT
            PO.ID AS po_id,
            PO.StringID AS po_number,
            PO.Date AS order_date,
            PO.DateNeeded AS date_needed,
            COALESCE(B.ScreenDescription, B.Description, B.AbbreviatedDesc) AS vendor_name,
            PO.Status AS status
        FROM [dbo].[PO] PO
        LEFT JOIN [dbo].[Business] B ON PO.Vendor = B.ID
        INNER JOIN [dbo].[PO_Item] PI ON PO.ID = PI.PO
        WHERE PO.Void = 0
        AND PI.Void = 0
        {where_clause}
        ORDER BY PO.StringID DESC
    """)
    
    with engine.connect() as conn:
        rows = conn.execute(sql_stmt, params)
        return [dict(r._mapping) for r in rows]


def fetch_po_items(po_id: int = None, po_string_id: str = None):
    """
    Fetch items for a specific purchase order.
    Returns detailed information about each item including quantities.
    """
    engine = get_metadata_engine()
    params = {}
    
    if po_id:
        where_clause = "PO.ID = :po_id"
        params["po_id"] = po_id
    elif po_string_id:
        where_clause = "PO.StringID = :po_string_id"
        params["po_string_id"] = po_string_id
    else:
        return []
    
    sql_stmt = text(f"""
        SELECT
            PI.ID AS item_id,
            PO.ID AS po_id,
            PO.StringID AS po_number,
            PO.Date AS po_date,
            COALESCE(B.ScreenDescription, B.Description, B.AbbreviatedDesc) AS vendor_name,
            COALESCE(P.Description, CAST(PI.Part AS varchar(50))) AS part,
            PI.Modifier AS modifier,
            PI.Part AS part_id,
            PI.QtyOrdered AS qty_ordered,
            PI.QtyReceived AS qty_received,
            (PI.QtyOrdered - PI.QtyReceived) AS qty_remaining,
            PI.Price,
            PI.ETA,
            PI.LastReceived,
            CAST(PI.Project AS varchar(50)) AS project,
            CAST(PI.Project AS varchar(50)) AS project_id,
            COALESCE(D.Description, CAST(PI.Drawing AS varchar(50))) AS drawing,
            CAST(PI.Drawing AS varchar(50)) AS drawing_id
        FROM [dbo].[PO] PO
        INNER JOIN [dbo].[PO_Item] PI ON PO.ID = PI.PO
        LEFT JOIN [dbo].[Business] B ON PO.Vendor = B.ID
        LEFT JOIN [dbo].[Part] P ON PI.Part = P.ID
        LEFT JOIN [dbo].[Project_Phase] D ON PI.Drawing = D.ID
        WHERE {where_clause}
        AND PO.Void = 0
        AND PI.Void = 0
        ORDER BY PI.POItemNumber
    """)
    
    with engine.connect() as conn:
        rows = conn.execute(sql_stmt, params)
        return [dict(r._mapping) for r in rows]


def search_pos(search_term: str = None):
    """
    Search for POs by PO number or vendor name.
    """
    engine = get_metadata_engine()
    
    if not search_term:
        return []
    
    sql_stmt = text("""
        SELECT DISTINCT TOP 50
            PO.ID AS po_id,
            PO.StringID AS po_number,
            PO.Date AS order_date,
            COALESCE(B.ScreenDescription, B.Description, B.AbbreviatedDesc) AS vendor_name,
            PO.Status AS status,
            COUNT(PI.ID) AS item_count
        FROM [dbo].[PO] PO
        LEFT JOIN [dbo].[Business] B ON PO.Vendor = B.ID
        LEFT JOIN [dbo].[PO_Item] PI ON PO.ID = PI.PO AND PI.Void = 0
        WHERE PO.Void = 0
        AND (
            PO.StringID LIKE :search_pattern
            OR B.Description LIKE :search_pattern
            OR B.ScreenDescription LIKE :search_pattern
            OR B.AbbreviatedDesc LIKE :search_pattern
        )
        GROUP BY
            PO.ID,
            PO.StringID,
            PO.Date,
            B.ScreenDescription,
            B.Description,
            B.AbbreviatedDesc,
            PO.Status
        ORDER BY PO.StringID DESC
    """)
    
    with engine.connect() as conn:
        rows = conn.execute(sql_stmt, {"search_pattern": f"%{search_term}%"})
        return [dict(r._mapping) for r in rows]
