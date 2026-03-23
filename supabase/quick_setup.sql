-- Strategy 5.x Quick Setup - All tables, views, and seed data
-- Run this in Supabase SQL Editor in one go

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Trigger function for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

