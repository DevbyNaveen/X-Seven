-- Migration: Add owner_id to businesses table
-- Date: 2025-09-16
-- Description: Add owner_id column to businesses table to track business owners

-- Add owner_id column to businesses table
ALTER TABLE businesses ADD COLUMN owner_id UUID REFERENCES auth.users(id);

-- Create index on owner_id for better performance
CREATE INDEX IF NOT EXISTS ix_businesses_owner_id ON businesses (owner_id);
