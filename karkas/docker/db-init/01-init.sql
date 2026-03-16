-- KARKAS Database Initialization Script
-- This script runs automatically when the PostgreSQL container starts for the first time

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Create schema
CREATE SCHEMA IF NOT EXISTS karkas;

-- Set search path
SET search_path TO karkas, public;

-- Create custom enum types for the application
-- These match the enums defined in server/database/config.py

-- Faction enum
DO $$ BEGIN
    CREATE TYPE karkas.faction AS ENUM ('red', 'blue', 'neutral');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Unit type enum
DO $$ BEGIN
    CREATE TYPE karkas.unit_type AS ENUM (
        'infantry', 'armor', 'mechanized', 'artillery', 'air_defense',
        'rotary', 'fixed_wing', 'support', 'headquarters', 'recon',
        'engineer', 'logistics'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Echelon enum
DO $$ BEGIN
    CREATE TYPE karkas.echelon AS ENUM (
        'squad', 'platoon', 'company', 'battalion', 'regiment',
        'brigade', 'division', 'corps', 'army'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Posture enum
DO $$ BEGIN
    CREATE TYPE karkas.posture AS ENUM (
        'attack', 'defend', 'move', 'recon', 'support',
        'reserve', 'retreat', 'disengaged'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Mobility class enum
DO $$ BEGIN
    CREATE TYPE karkas.mobility_class AS ENUM (
        'foot', 'wheeled', 'tracked', 'rotary', 'fixed_wing'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Sensor type enum
DO $$ BEGIN
    CREATE TYPE karkas.sensor_type AS ENUM (
        'visual', 'thermal', 'radar', 'sigint', 'acoustic',
        'satellite', 'human_intel'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Order type enum
DO $$ BEGIN
    CREATE TYPE karkas.order_type AS ENUM (
        'move', 'attack', 'defend', 'support', 'recon',
        'withdraw', 'resupply', 'hold'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Route preference enum
DO $$ BEGIN
    CREATE TYPE karkas.route_preference AS ENUM (
        'fastest', 'covered', 'specified', 'avoid_enemy'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Rules of engagement enum
DO $$ BEGIN
    CREATE TYPE karkas.roe AS ENUM (
        'weapons_free', 'weapons_hold', 'weapons_tight'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Objective type enum
DO $$ BEGIN
    CREATE TYPE karkas.objective_type AS ENUM (
        'position', 'unit', 'zone'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Turn phase enum
DO $$ BEGIN
    CREATE TYPE karkas.turn_phase AS ENUM (
        'planning', 'execution', 'reporting'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Precipitation enum
DO $$ BEGIN
    CREATE TYPE karkas.precipitation AS ENUM (
        'none', 'light', 'moderate', 'heavy'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Visibility enum
DO $$ BEGIN
    CREATE TYPE karkas.visibility AS ENUM (
        'clear', 'haze', 'fog', 'smoke'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Contact confidence enum
DO $$ BEGIN
    CREATE TYPE karkas.contact_confidence AS ENUM (
        'confirmed', 'probable', 'suspected', 'unknown'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Victory condition type enum
DO $$ BEGIN
    CREATE TYPE karkas.victory_condition_type AS ENUM (
        'territorial', 'attrition', 'time', 'objective'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Create spatial index function for convenience
CREATE OR REPLACE FUNCTION karkas.create_spatial_index(
    table_name TEXT,
    column_name TEXT DEFAULT 'geom'
)
RETURNS VOID AS $$
BEGIN
    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS %I ON karkas.%I USING GIST (%I)',
        table_name || '_' || column_name || '_idx',
        table_name,
        column_name
    );
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL ON SCHEMA karkas TO karkas;
GRANT ALL ON ALL TABLES IN SCHEMA karkas TO karkas;
GRANT ALL ON ALL SEQUENCES IN SCHEMA karkas TO karkas;

-- Verify PostGIS is working
SELECT PostGIS_Version();
