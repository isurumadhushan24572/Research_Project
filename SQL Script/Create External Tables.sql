
USE Teacher_Trasnsfer
GO
-- --- Create Master Key -------
-- CREATE MASTER KEY ENCRYPTION BY PASSWORD ='Pzt7$mki';

--- Create Database Scoped Credentials ----
CREATE DATABASE SCOPED CREDENTIAL credential_bd
WITH IDENTITY = 'Managed Identity';

--- Create External Data Source for Silver -------

CREATE EXTERNAL DATA SOURCE source_silver
WITH (
    LOCATION = 'https://zonal.blob.core.windows.net/silver',
    CREDENTIAL = credential_bd
)

--------------------------------------------------

--- Create External Data Source for Gold -------
CREATE EXTERNAL DATA SOURCE source_gold
WITH
(
    LOCATION = 'https://zonal.blob.core.windows.net/gold', 
    CREDENTIAL = credential_bd 
)


--- Create an external file format for Parquet files.
CREATE EXTERNAL FILE FORMAT format_parquet
WITH 
(
        FORMAT_TYPE = PARQUET,
        DATA_COMPRESSION = 'org.apache.hadoop.io.compress.SnappyCodec'
);


-----------------------------------------------------------------------


--- Create external table for Teacher_details ----

CREATE EXTERNAL TABLE gold.ext_teacher (
    School_Census_No VARCHAR(50),
    NIC VARCHAR(20),
    Payroll_No INT,
    Title VARCHAR(20),
    Teacher_Name VARCHAR(100),
    Position VARCHAR(50),
    Birth_Date DATE,
    Gender VARCHAR(10),
    Ethnicity VARCHAR(50),
    Religion VARCHAR(50),
    Marital_Status VARCHAR(20),
    Highest_Edu_Qualification VARCHAR(100),
    Subject_Stream_AL VARCHAR(100),
    Field_Basic_Degree VARCHAR(100),
    Highest_Prof_Qualification VARCHAR(100),
    Appointment_Day DATE,
    Section_Of_Appointment VARCHAR(100),
    Medium_Of_Appointment VARCHAR(50),
    TT_Certificate BIT,
    NCOE_Diploma BIT,
    BEd BIT,
    PG_Dip_Edu BIT,
    MEd BIT,
    Not_Obtained BIT,
    Assigned_School_Day DATE,
    Mobile_Number VARCHAR(20)
)
WITH (
    LOCATION = 'Teacher_Details/',
    DATA_SOURCE = source_silver,
    FILE_FORMAT = format_parquet
);





--- Create external table for School_details ----

DROP EXTERNAL TABLE gold.ext_school

CREATE EXTERNAL TABLE gold.ext_school (

    School_ID VARCHAR(50),
    School_Name VARCHAR(100),
    Division VARCHAR(50),
    Type VARCHAR(50),
    Category_CODE VARCHAR(50),
    Reputation VARCHAR(50),
    Grade VARCHAR(20),
    Category_Name VARCHAR(100),
    "Primary" BIT,
    Secondary BIT,
    "A/L_General" BIT,
    "A/L_Science" BIT,
    "A/L_Technology" BIT,
    "A/L_Commerce" BIT,
    "A/L_Arts" BIT,
    School_Address VARCHAR(200)


)
WITH (
    LOCATION = 'School_Details/',
    DATA_SOURCE = source_silver,
    FILE_FORMAT = format_parquet
);



--- Create external table for Subject_details ----

CREATE EXTERNAL TABLE gold.ext_subject(
    
    SECTION VARCHAR(50),
    SUBJECT VARCHAR(100)

)
WITH
(
    LOCATION = 'Subject_Details/',
    DATA_SOURCE = source_silver,
    FILE_FORMAT = format_parquet
);


-- EXTERNAL TABLES

SELECT * FROM gold.ext_teacher 

SELECT * FROM gold.ext_school

SELECT * FROM gold.ext_subject 


