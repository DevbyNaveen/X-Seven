-- Migration: Add email column to businesses table
-- Date: 2025-09-19
-- Description: Add email column to businesses table for analytics and faster lookups

-- Add email column to businesses table
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS email TEXT UNIQUE;

-- Create index on email for better performance
CREATE INDEX IF NOT EXISTS idx_businesses_email ON businesses (email);

-- Populate email column from contact_info for existing businesses
UPDATE businesses
SET email = contact_info->>'email'
WHERE email IS NULL AND contact_info->>'email' IS NOT NULL;

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE 'Migration completed: Added email column to businesses table';
    RAISE NOTICE 'Email column populated from contact_info for existing businesses';
    RAISE NOTICE 'Index created on email column for performance';
END $$;
