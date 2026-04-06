-- Update Receiving_Submissions table to link with PO system
-- Add foreign key reference to PO_Item table

-- Check if column already exists
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'Receiving_Submissions' 
               AND COLUMN_NAME = 'POItem_ID')
BEGIN
    ALTER TABLE [dbo].[Receiving_Submissions]
    ADD [POItem_ID] INT NULL;
    
    PRINT 'Added POItem_ID column to Receiving_Submissions table';
END
ELSE
BEGIN
    PRINT 'POItem_ID column already exists';
END

-- Create index on POItem_ID for faster queries
IF NOT EXISTS (SELECT * FROM sys.indexes 
               WHERE name = 'idx_po_item_id' 
               AND object_id = OBJECT_ID('dbo.Receiving_Submissions'))
BEGIN
    CREATE INDEX idx_po_item_id ON [dbo].[Receiving_Submissions] ([POItem_ID]);
    PRINT 'Created index on POItem_ID';
END
ELSE
BEGIN
    PRINT 'Index on POItem_ID already exists';
END

-- Note: We're not adding a foreign key constraint to allow flexibility
-- The PO system is in a different database (CrowsNest) than receiving data (CNtempGuru)
-- POItem_ID is a logical reference, not a physical foreign key

PRINT 'Receiving schema updated successfully for PO integration';
