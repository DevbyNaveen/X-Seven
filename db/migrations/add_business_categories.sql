-- Migration: Add Business Categories
-- Date: 2024-08-19
-- Description: Add category and category_config columns to businesses table

-- Add category column
ALTER TABLE businesses ADD COLUMN category VARCHAR(50);

-- Add category_config column
ALTER TABLE businesses ADD COLUMN category_config JSON;

-- Update existing businesses with food_hospitality category
UPDATE businesses 
SET category = 'food_hospitality', 
    category_config = '{
        "has_tables": true, 
        "has_kitchen": true, 
        "delivery_available": true, 
        "qr_ordering": true, 
        "reservation_system": true, 
        "menu_categories": ["Beverages", "Appetizers", "Main Dishes", "Desserts", "Specials"], 
        "default_services": ["Dine-in", "Takeout", "Delivery"], 
        "pricing_tier": "basic"
    }'
WHERE name IN ('Cafe2211', 'Grand Cafe', 'Quick Bites', 'Sweet Dreams');

-- Create index on category for better performance
CREATE INDEX IF NOT EXISTS ix_businesses_category ON businesses (category);
