-- E-ACIS: Full PostgreSQL DDL
-- Generated: 2026-04-18
-- This file provides a full schema approximation for the E-ACIS application.
-- It includes type definitions, tables, indexes, example views, and triggers
-- Intended for local/dev use. Review before applying to production.

-- Set timezone
SET timezone = 'UTC';

-- ===================================================================
-- Role / DB creation (run as superuser or adapt to your environment)
-- ===================================================================
-- CREATE ROLE eacis WITH LOGIN PASSWORD '<REPLACE_WITH_STRONG_PASSWORD>';
-- CREATE DATABASE eacis OWNER eacis;
-- 
-- Connect to the `eacis` database before running the rest of this file.

-- ===================================================================
-- ENUM / TYPE DEFINITIONS
-- ===================================================================
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_roles') THEN
        CREATE TYPE user_roles AS ENUM ('customer','seller','admin');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_status') THEN
        CREATE TYPE order_status AS ENUM ('pending','paid','packed','shipped','delivered','past_due','refunded','cancelled');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_method') THEN
        CREATE TYPE payment_method AS ENUM ('full_pay','installment');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'voucher_type') THEN
        CREATE TYPE voucher_type AS ENUM ('percent','fixed');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'stock_movement_type') THEN
        CREATE TYPE stock_movement_type AS ENUM ('SALE','RETURN','RESTOCK','ADJUSTMENT','CANCELLATION');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'installment_status') THEN
        CREATE TYPE installment_status AS ENUM ('active','completed','defaulted');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'schedule_status') THEN
        CREATE TYPE schedule_status AS ENUM ('pending','paid','past_due');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'inquiry_priority') THEN
        CREATE TYPE inquiry_priority AS ENUM ('low','medium','high','urgent');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'inquiry_status') THEN
        CREATE TYPE inquiry_status AS ENUM ('open','in_progress','resolved','closed');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invoice_status') THEN
        CREATE TYPE invoice_status AS ENUM ('issued','paid','void');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'refund_status') THEN
        CREATE TYPE refund_status AS ENUM ('requested','processed','failed');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'rrt_status') THEN
        CREATE TYPE rrt_status AS ENUM ('pending','accepted','rejected','refund_requested','refunded');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'loyalty_type') THEN
        CREATE TYPE loyalty_type AS ENUM ('earn','redeem','expire','adjust');
    END IF;
END $$;

-- ===================================================================
-- Tables
-- ===================================================================

-- users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role user_roles NOT NULL,
    full_name VARCHAR(255),
    first_name VARCHAR(100),
    middle_name VARCHAR(100),
    last_name VARCHAR(100),
    suffix VARCHAR(20),
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    barangay VARCHAR(120),
    city_municipality VARCHAR(120),
    province VARCHAR(120),
    region VARCHAR(120),
    postal_code VARCHAR(20),
    business_name VARCHAR(255),
    business_permit_path VARCHAR(500),
    barangay_permit_path VARCHAR(500),
    mayors_permit_path VARCHAR(500),
    seller_verification_status VARCHAR(20) DEFAULT 'pending',
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    email_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    loyalty_points INTEGER DEFAULT 0,
    seller_code VARCHAR(10) UNIQUE
);

-- addresses
CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label VARCHAR(50),
    recipient_name VARCHAR(255),
    phone VARCHAR(32),
    address_line1 VARCHAR(255) NOT NULL,
    address_line2 VARCHAR(255),
    barangay VARCHAR(120),
    city_municipality VARCHAR(120),
    province VARCHAR(120),
    region VARCHAR(120),
    postal_code VARCHAR(20),
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_addresses_user_id ON addresses(user_id);

-- products
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    product_ref VARCHAR(30) UNIQUE NOT NULL,
    seller_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    price NUMERIC(12,2) NOT NULL,
    compare_price NUMERIC(12,2),
    stock INTEGER DEFAULT 0,
    low_stock_threshold INTEGER DEFAULT 5,
    warranty_months INTEGER DEFAULT 12,
    installment_enabled BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    weight_kg NUMERIC(6,2),
    image_url VARCHAR(500),
    specs JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_products_seller ON products(seller_id);
CREATE INDEX IF NOT EXISTS idx_products_ref ON products(product_ref);

-- product_images
CREATE TABLE IF NOT EXISTS product_images (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    position INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- stock movements (audit trail)
CREATE TABLE IF NOT EXISTS stock_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    type stock_movement_type NOT NULL,
    reference VARCHAR(80),
    note VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id);

-- orders and items
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_ref VARCHAR(30) UNIQUE,
    customer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status order_status,
    subtotal NUMERIC(12,2),
    discount NUMERIC(12,2) DEFAULT 0,
    shipping_fee NUMERIC(12,2) DEFAULT 0,
    tax NUMERIC(12,2) DEFAULT 0,
    total NUMERIC(12,2),
    voucher_id INTEGER REFERENCES vouchers(id) ON DELETE SET NULL,
    loyalty_redeemed INTEGER DEFAULT 0,
    payment_method payment_method,
    payment_ref VARCHAR(100),
    shipping_address JSONB,
    tracking_number VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    paid_at TIMESTAMPTZ,
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);

CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    quantity INTEGER,
    unit_price NUMERIC(12,2),
    subtotal NUMERIC(12,2)
);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);

-- carts
CREATE TABLE IF NOT EXISTS carts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    items JSONB,
    voucher_code VARCHAR(50),
    loyalty_redeemed INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- invoices
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    invoice_ref VARCHAR(30) UNIQUE NOT NULL,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    seller_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subtotal NUMERIC(12,2) DEFAULT 0,
    discount_total NUMERIC(12,2) DEFAULT 0,
    tax_total NUMERIC(12,2) DEFAULT 0,
    shipping_total NUMERIC(12,2) DEFAULT 0,
    grand_total NUMERIC(12,2) DEFAULT 0,
    status invoice_status DEFAULT 'issued',
    issued_at TIMESTAMPTZ DEFAULT now(),
    due_at TIMESTAMPTZ DEFAULT (now() + INTERVAL '7 days')
);

-- vouchers and usage logs
CREATE TABLE IF NOT EXISTS vouchers (
    id SERIAL PRIMARY KEY,
    voucher_ref VARCHAR(30) UNIQUE,
    code VARCHAR(50) UNIQUE,
    discount_type voucher_type,
    discount_value NUMERIC(10,2),
    min_order_amount NUMERIC(12,2) DEFAULT 0,
    max_uses INTEGER,
    uses_count INTEGER DEFAULT 0,
    per_user_limit INTEGER DEFAULT 1,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    seller_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    combinable BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS voucher_usage_logs (
    id SERIAL PRIMARY KEY,
    voucher_id INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    discount_applied NUMERIC(12,2) DEFAULT 0,
    used_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_voucher_usage_voucher ON voucher_usage_logs(voucher_id);

-- returns & refunds
CREATE TABLE IF NOT EXISTS return_requests (
    id SERIAL PRIMARY KEY,
    rrt_ref VARCHAR(30) UNIQUE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    customer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reason VARCHAR(255),
    description TEXT,
    evidence_urls JSONB,
    status rrt_status,
    seller_notes TEXT,
    restocked_qty INTEGER,
    refund_amount NUMERIC(12,2),
    admin_notes TEXT,
    paymongo_refund_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS refund_transactions (
    id SERIAL PRIMARY KEY,
    refund_ref VARCHAR(30) UNIQUE NOT NULL,
    return_request_id INTEGER NOT NULL REFERENCES return_requests(id) ON DELETE CASCADE,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    status refund_status DEFAULT 'requested',
    method VARCHAR(50) DEFAULT 'original_payment_method',
    processed_at TIMESTAMPTZ DEFAULT now()
);

-- reviews and stars
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL,
    title VARCHAR(255),
    body TEXT,
    is_approved BOOLEAN DEFAULT TRUE,
    is_anonymous BOOLEAN DEFAULT FALSE,
    reviewer_name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uix_product_user_review UNIQUE(product_id, user_id)
);

CREATE TABLE IF NOT EXISTS product_stars (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uix_product_user_star UNIQUE(product_id, user_id)
);

-- audit, OTP, trusted devices, loyalty
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    actor_name VARCHAR(255),
    role VARCHAR(50),
    action VARCHAR(100),
    module VARCHAR(50),
    target_ref VARCHAR(100),
    meta JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS otp_challenges (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    email VARCHAR(255) NOT NULL,
    purpose VARCHAR(50) NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    attempt_count INTEGER DEFAULT 0 NOT NULL,
    max_attempts INTEGER DEFAULT 5 NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    sent_to VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now(),
    verified_at TIMESTAMPTZ,
    failure_reason VARCHAR(100),
    meta JSONB
);

CREATE TABLE IF NOT EXISTS trusted_devices (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    device_name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS loyalty_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    type loyalty_type,
    points INTEGER,
    reference VARCHAR(100),
    note VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- inquiry tickets and replies
CREATE TABLE IF NOT EXISTS inquiry_tickets (
    id SERIAL PRIMARY KEY,
    ticket_ref VARCHAR(30) UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
    subject VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    priority inquiry_priority DEFAULT 'medium',
    status inquiry_status DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS inquiry_replies (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES inquiry_tickets(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- installment plans and schedules
CREATE TABLE IF NOT EXISTS installment_plans (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    months INTEGER,
    monthly_amount NUMERIC(12,2),
    downpayment NUMERIC(12,2) DEFAULT 0,
    total_interest NUMERIC(12,2) DEFAULT 0,
    status installment_status
);

CREATE TABLE IF NOT EXISTS installment_schedule (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER REFERENCES installment_plans(id) ON DELETE CASCADE,
    due_date DATE,
    amount NUMERIC(12,2),
    status schedule_status,
    paid_at TIMESTAMPTZ,
    payment_ref VARCHAR(100)
);

-- voucher usage audit already created above

-- ===================================================================
-- Trigger functions and triggers
-- ===================================================================

-- Sync product.stock from stock_movements (keeps a cached value correct)
CREATE OR REPLACE FUNCTION fn_sync_product_stock() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    pid INTEGER;
BEGIN
    IF (TG_OP = 'INSERT') THEN
        pid := NEW.product_id;
    ELSIF (TG_OP = 'UPDATE') THEN
        pid := NEW.product_id;
    ELSIF (TG_OP = 'DELETE') THEN
        pid := OLD.product_id;
    END IF;

    UPDATE products
    SET stock = COALESCE((SELECT SUM(quantity) FROM stock_movements WHERE product_id = pid), 0)
    WHERE id = pid;

    RETURN NULL;
END; $$;

DROP TRIGGER IF EXISTS trg_stock_sync ON stock_movements;
CREATE TRIGGER trg_stock_sync AFTER INSERT OR UPDATE OR DELETE ON stock_movements
FOR EACH ROW EXECUTE FUNCTION fn_sync_product_stock();

-- Increment/decrement voucher uses_count when usage logs are inserted/deleted
CREATE OR REPLACE FUNCTION fn_inc_voucher_uses() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE vouchers SET uses_count = COALESCE(uses_count, 0) + 1 WHERE id = NEW.voucher_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE vouchers SET uses_count = GREATEST(COALESCE(uses_count, 0) - 1, 0) WHERE id = OLD.voucher_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END; $$;

DROP TRIGGER IF EXISTS trg_voucher_usage_inc ON voucher_usage_logs;
CREATE TRIGGER trg_voucher_usage_inc AFTER INSERT OR DELETE ON voucher_usage_logs
FOR EACH ROW EXECUTE FUNCTION fn_inc_voucher_uses();

-- ===================================================================
-- Views (useful read-only reports)
-- ===================================================================

-- Customer total spent summary (paid/delivered orders only)
CREATE OR REPLACE VIEW vw_customer_total_spent AS
SELECT u.id AS user_id, u.email, COALESCE(SUM(o.total), 0)::NUMERIC(18,2) AS total_spent
FROM users u
LEFT JOIN orders o ON o.customer_id = u.id AND o.status IN ('paid','delivered')
GROUP BY u.id, u.email;

-- Low stock products
CREATE OR REPLACE VIEW vw_low_stock_products AS
SELECT p.id, p.product_ref, p.name, p.stock, p.low_stock_threshold, (p.stock <= p.low_stock_threshold) AS is_low_stock
FROM products p
WHERE p.is_active = TRUE;

-- Orders per day (last 30 days)
CREATE OR REPLACE VIEW vw_orders_daily AS
SELECT DATE(created_at) AS day, COUNT(*) AS orders_count, COALESCE(SUM(total),0)::NUMERIC(18,2) AS total_value
FROM orders
WHERE created_at >= (now() - INTERVAL '30 days')
GROUP BY DATE(created_at)
ORDER BY DATE(created_at) DESC;

-- ===================================================================
-- Helpful indexes
-- ===================================================================
CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user ON reviews(user_id);

-- ===================================================================
-- Notes & usage
-- ===================================================================
-- 1) Run this file in a fresh database, or inspect and run specific sections.
-- 2) To create the database and user (superuser required):
--    CREATE ROLE eacis WITH LOGIN PASSWORD '<REPLACE_WITH_STRONG_PASSWORD>';
--    CREATE DATABASE eacis OWNER eacis;
--    
-- 3) To load: psql -U postgres -d eacis -f eacis_db_full_postgres.sql
-- 4) The triggers and views provide basic read/write automation; extend as needed.

-- EOF
