-- Migration: 001_init.sql
-- Description: Initialize loans table and insert initial seed dataset

CREATE TABLE IF NOT EXISTS loans (
    id SERIAL PRIMARY KEY,
    borrower_name TEXT NOT NULL,
    loan_amount NUMERIC(14,2) NOT NULL,
    property_city TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed initial loans (5+ rows required by assignment specification)
INSERT INTO loans (borrower_name, loan_amount, property_city, status, created_at)
VALUES
    ('Alice Henderson', 350000.00, 'Austin', 'APPROVED', NOW() - INTERVAL '10 days'),
    ('Bob Martinez', 485000.50, 'Seattle', 'PENDING', NOW() - INTERVAL '7 days'),
    ('Catherine Chen', 720000.00, 'San Francisco', 'APPROVED', NOW() - INTERVAL '5 days'),
    ('David Okafor', 260000.00, 'Chicago', 'REJECTED', NOW() - INTERVAL '3 days'),
    ('Elena Rostova', 510000.00, 'Denver', 'PENDING', NOW() - INTERVAL '2 days'),
    ('Faisal Al-Mansoor', 640000.00, 'Boston', 'APPROVED', NOW() - INTERVAL '1 day')
ON CONFLICT DO NOTHING;
