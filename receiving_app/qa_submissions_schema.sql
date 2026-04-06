-- QA_Submissions Table Creation Script
-- This table stores all QA submission data with issue tracking

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[QA_Submissions]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[QA_Submissions] (
        [ID] INT PRIMARY KEY IDENTITY(1,1),
        [Project] NVARCHAR(100) NOT NULL,
        [Drawing] NVARCHAR(100) NOT NULL,
        [Elevation] NVARCHAR(100) NOT NULL,
        [RoomNumber] NVARCHAR(50) NOT NULL,
        [QaCheck] NVARCHAR(20) NOT NULL,  -- 'Pass' or 'Fail'
        [IssueCategory] NVARCHAR(MAX) NULL,  -- Semicolon-separated list of issues
        [Description] NVARCHAR(MAX) NULL,
        [Resubmit] BIT NOT NULL DEFAULT 0,
        [Timestamp] DATETIME2 NOT NULL DEFAULT GETUTCDATE()
    );

    -- Create indexes for faster queries
    CREATE INDEX idx_project ON [dbo].[QA_Submissions] ([Project]);
    CREATE INDEX idx_drawing ON [dbo].[QA_Submissions] ([Drawing]);
    CREATE INDEX idx_qa_check ON [dbo].[QA_Submissions] ([QaCheck]);
    CREATE INDEX idx_timestamp ON [dbo].[QA_Submissions] ([Timestamp]);

    PRINT 'QA_Submissions table created successfully.';
END
ELSE
BEGIN
    PRINT 'QA_Submissions table already exists.';
END
