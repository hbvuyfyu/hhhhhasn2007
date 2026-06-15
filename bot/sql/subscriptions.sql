-- =====================================================
-- نظام الاشتراكات — جداول إضافية
-- شغّل هذا بعد full_setup.sql أو كمهاجرة مستقلة
-- =====================================================

CREATE TABLE IF NOT EXISTS subscription_plans (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    duration_days INTEGER NOT NULL,
    price        DECIMAL(10,2) NOT NULL,
    daily_limit  INTEGER NOT NULL,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id               SERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL,
    plan_id          INTEGER REFERENCES subscription_plans(id),
    plan_name        TEXT NOT NULL DEFAULT '',
    daily_limit      INTEGER NOT NULL DEFAULT 10,
    daily_used       INTEGER DEFAULT 0,
    last_reset_date  DATE DEFAULT CURRENT_DATE,
    start_date       TIMESTAMP NOT NULL DEFAULT NOW(),
    end_date         TIMESTAMP NOT NULL,
    status           TEXT DEFAULT 'active',
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payment_settings (
    id               SERIAL PRIMARY KEY,
    method           TEXT UNIQUE NOT NULL,
    display_name     TEXT NOT NULL,
    address          TEXT DEFAULT '',
    instructions     TEXT DEFAULT '',
    is_active        BOOLEAN DEFAULT TRUE,
    binance_api_key  TEXT DEFAULT '',
    binance_api_secret TEXT DEFAULT '',
    updated_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payment_requests (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    user_name       TEXT DEFAULT '',
    user_username   TEXT DEFAULT '',
    plan_id         INTEGER REFERENCES subscription_plans(id),
    plan_name       TEXT NOT NULL DEFAULT '',
    method          TEXT NOT NULL,
    amount          DECIMAL(10,2) NOT NULL DEFAULT 0,
    transaction_id  TEXT DEFAULT '',
    proof_file_id   TEXT DEFAULT '',
    status          TEXT DEFAULT 'pending',
    admin_id        BIGINT,
    created_at      TIMESTAMP DEFAULT NOW(),
    processed_at    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user   ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_pay_requests_status  ON payment_requests(status);
CREATE INDEX IF NOT EXISTS idx_pay_requests_user    ON payment_requests(user_id);

-- الباقات الافتراضية
INSERT INTO subscription_plans (name, duration_days, price, daily_limit) VALUES
('باقة يومية',   1,  2.00, 10),
('باقة أسبوعية', 7,  5.00, 15),
('باقة شهرية',  30, 15.00, 20)
ON CONFLICT DO NOTHING;

-- إعدادات الدفع الافتراضية
INSERT INTO payment_settings (method, display_name, address, instructions) VALUES
('usdt',          'USDT (TRC20)',   '', 'أرسل USDT عبر شبكة TRC20 ثم ابعث رقم عملية التحويل'),
('sham_cash',     'شام كاش',       '', 'أرسل المبلغ عبر شام كاش ثم ابعث صورة الإثبات'),
('syriatel_cash', 'سرياتيل كاش',   '', 'أرسل المبلغ عبر سرياتيل كاش ثم ابعث صورة الإثبات')
ON CONFLICT (method) DO NOTHING;

-- تحقق
SELECT '✅ subscription_plans' AS t, COUNT(*) FROM subscription_plans
UNION ALL
SELECT '✅ payment_settings',       COUNT(*) FROM payment_settings;
