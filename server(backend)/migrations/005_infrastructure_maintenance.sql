-- Phase 8 infrastructure and maintenance metadata.
ALTER TABLE assets ADD COLUMN criticality VARCHAR(20) NOT NULL DEFAULT 'MEDIUM';
ALTER TABLE assets ADD COLUMN facility VARCHAR(100);
ALTER TABLE maintenance_tasks ADD COLUMN required_parts JSON;
ALTER TABLE maintenance_tasks ADD COLUMN priority VARCHAR(20) NOT NULL DEFAULT 'MEDIUM';
ALTER TABLE maintenance_tasks ADD COLUMN maintenance_state VARCHAR(30) NOT NULL DEFAULT 'NOT_DUE';
ALTER TABLE maintenance_tasks ADD COLUMN readiness VARCHAR(30) NOT NULL DEFAULT 'READY';
