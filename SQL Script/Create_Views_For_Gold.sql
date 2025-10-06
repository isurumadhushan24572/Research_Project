----------------------
-- School_Details View
----------------------
CREATE VIEW gold.school_vw
AS
SELECT *
FROM 
    OPENROWSET(
        BULK 'https://zonal.blob.core.windows.net/silver/School_Details/part-*.parquet',
        FORMAT = 'PARQUET'
    ) vw1

    
----------------------
-- Teacher_Details View
----------------------
CREATE VIEW gold.Teacher_vw
AS
SELECT *
FROM 
    OPENROWSET(
        BULK 'https://zonal.blob.core.windows.net/silver/Teacher_Details/part-*.parquet',
        FORMAT = 'PARQUET'
    ) vw2


----------------------
-- Subject_Details View
----------------------


CREATE VIEW gold.Subject_vw
AS
SELECT *
FROM 
    OPENROWSET(
        BULK 'https://zonal.blob.core.windows.net/silver/Subject_Details/part-*.parquet',
        FORMAT = 'PARQUET'
    ) vw3




