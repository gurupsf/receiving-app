-- Receiving Submissions Table Creation Script
-- This table stores all receiving data with item status and delivery tracking

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Receiving_Submissions]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[Receiving_Submissions] (
        [ID] INT PRIMARY KEY IDENTITY(1,1),
        [Project] NVARCHAR(100) NOT NULL,
        [Drawing] NVARCHAR(100) NOT NULL,
        [PO_Number] NVARCHAR(100) NOT NULL,
        [Material_ID] NVARCHAR(100) NOT NULL,
        [Supplier] NVARCHAR(200) NULL,
        [Quantity_Ordered] INT NOT NULL,
        [Quantity_Received] INT NOT NULL,
        [Defective_Count] INT NOT NULL DEFAULT 0,
        [Item_Status] NVARCHAR(20) NOT NULL,  -- 'Accepted' or 'Rejected'
        [Order_Date] DATETIME2 NULL,  -- From purchasing system
        [Received_Date] DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
        [Delivery_Days] AS DATEDIFF(DAY, [Order_Date], [Received_Date]),  -- Computed column
        [Notes] NVARCHAR(MAX) NULL,
        [Timestamp] DATETIME2 NOT NULL DEFAULT GETUTCDATE()
    );

    -- Create indexes for faster queries
    CREATE INDEX idx_project ON [dbo].[Receiving_Submissions] ([Project]);
    CREATE INDEX idx_po_number ON [dbo].[Receiving_Submissions] ([PO_Number]);
    CREATE INDEX idx_supplier ON [dbo].[Receiving_Submissions] ([Supplier]);
    CREATE INDEX idx_item_status ON [dbo].[Receiving_Submissions] ([Item_Status]);
    CREATE INDEX idx_received_date ON [dbo].[Receiving_Submissions] ([Received_Date]);
    CREATE INDEX idx_material_id ON [dbo].[Receiving_Submissions] ([Material_ID]);

    PRINT 'Receiving_Submissions table created successfully.';
END
ELSE
BEGIN
    PRINT 'Receiving_Submissions table already exists.';
END

-- Optional: Create a view for supplier KPIs
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[vw_Supplier_KPIs]') AND type = 'V')
BEGIN
    EXEC('
    CREATE VIEW [dbo].[vw_Supplier_KPIs] AS
    SELECT 
        Supplier,
        COUNT(*) AS Total_Orders,
        SUM(Quantity_Received) AS Total_Quantity_Received,
        SUM(Defective_Count) AS Total_Defective,
        CAST(AVG(CAST(Defective_Count AS FLOAT)) AS DECIMAL(10,2)) AS Avg_Defective_Per_Order,
        CAST(AVG(CAST(Delivery_Days AS FLOAT)) AS DECIMAL(10,2)) AS Avg_Delivery_Days,
        CAST((SUM(CAST(Defective_Count AS FLOAT)) / NULLIF(SUM(Quantity_Received), 0)) * 100 AS DECIMAL(10,2)) AS Defect_Rate_Percent,
        COUNT(CASE WHEN Item_Status = ''Accepted'' THEN 1 END) AS Accepted_Count,
        COUNT(CASE WHEN Item_Status = ''Rejected'' THEN 1 END) AS Rejected_Count,
        MIN(Received_Date) AS First_Order_Date,
        MAX(Received_Date) AS Last_Order_Date
    FROM [dbo].[Receiving_Submissions]
    WHERE Supplier IS NOT NULL
    GROUP BY Supplier
    ');
    PRINT 'vw_Supplier_KPIs view created successfully.';
END
