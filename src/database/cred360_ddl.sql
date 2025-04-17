-- Drop tables if `customer_master` exist
DROP TABLE IF EXISTS customer_master;

-- Create `customer_master` table
CREATE TABLE customer_master (
    customer_id TEXT PRIMARY KEY NOT NULL,  -- Unique identifier for the customer
    company_name TEXT NOT NULL,             -- Name of the company
    contact_name TEXT,                      -- Name of the contact person
    contact_email TEXT,                     -- Email of the contact person
    contact_phone TEXT,                     -- Phone number of the contact person
    address TEXT,                           -- Address of the company
    city TEXT,                              -- City where the company is located
    state TEXT,                             -- State where the company is located
    zip_code INT,                           -- ZIP code of the company's location
    country TEXT,                           -- Country where the company is located
    account_creation_date DATE,             -- Date when the account was created
    constitution TEXT,                      -- Legal constitution of the company
    asset_class TEXT                        -- Classification of the company's assets
);

-- Drop tables if `loan_data` exist
DROP TABLE IF EXISTS loan_data;

-- Create `loan_data` table
CREATE TABLE loan_data (
    customer_id TEXT PRIMARY KEY NOT NULL,  -- Unique identifier for the customer (foreign key)
    loan_type_1 TEXT,                       -- Type of the first loan
    loan_type_2 TEXT,                       -- Type of the second loan
    loan1_amount FLOAT,                     -- Amount of the first loan
    loan_outstanding_1 FLOAT,               -- Outstanding amount of the first loan
    loan2_amount FLOAT,                     -- Amount of the second loan
    loan_outstanding_2 FLOAT,               -- Outstanding amount of the second loan
    loan1_interest FLOAT,                   -- Interest rate of the first loan
    loan2_interest FLOAT,                   -- Interest rate of the second loan
    date_last_sanction DATE,                -- Date of the last loan sanction
    date_lsr DATE,                          -- Date of the last LSR (Loan Sanction Report)
    date_valuation_report DATE,             -- Date of the last valuation report
    date_of_bank_credit_report DATE,        -- Date of the last bank credit report
    date_internal_rating DATE,              -- Date of the last internal rating
    date_external_rating DATE,              -- Date of the last external rating
    date_of_last_audit DATE,                -- Date of the last audit
    date_tev_report DATE,                   -- Date of the last TEV (Techno-Economic Viability) report
    date_stock_statement DATE,              -- Date of the last stock statement
    FOREIGN KEY(customer_id) REFERENCES customer_master(customer_id)  -- Foreign key constraint
);

-- Drop tables if `audit_llm_calls` exist
DROP TABLE IF EXISTS audit_llm_calls;

-- Create `audit_llm_calls` table
CREATE TABLE audit_llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,   -- Unique identifier for each call (auto-incremented)
    run_timestamp TEXT NOT NULL,            -- Timestamp when the run was initiated
    account_name TEXT NOT NULL,             -- Name of the account making the call
    call_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- Timestamp when the call was made
    model_name TEXT NOT NULL,               -- Name of the language model used
    call_purpose TEXT NOT NULL,             -- Purpose of the call
    langgraph_node TEXT,                    -- Node in the language graph (if applicable)
    input_tokens INTEGER NOT NULL,          -- Number of input tokens
    output_tokens INTEGER NOT NULL,         -- Number of output tokens
    total_tokens INTEGER NOT NULL,          -- Total number of tokens (input + output)
    status TEXT NOT NULL CHECK(status IN ('completed', 'failed'))  -- Status of the call (completed or failed)
);
