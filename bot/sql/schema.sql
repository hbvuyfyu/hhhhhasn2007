-- =====================================================
-- AK Jumper Bot - PostgreSQL Schema
-- Run this once against your Neon / Railway DB
-- =====================================================

-- ==================== Core tables ====================

CREATE TABLE IF NOT EXISTS users (
    user_id     BIGINT PRIMARY KEY,
    username    TEXT,
    name        TEXT,
    admin       INTEGER NOT NULL DEFAULT 0,
    allowed     INTEGER NOT NULL DEFAULT 0,
    banned      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT,
    last_use    TEXT,
    total_requests INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_users_allowed ON users (allowed);
CREATE INDEX IF NOT EXISTS idx_users_banned  ON users (banned);

CREATE TABLE IF NOT EXISTS allowed_users (
    user_id    BIGINT PRIMARY KEY,
    username   TEXT,
    name       TEXT,
    added_by   BIGINT,
    added_date TEXT
);

CREATE TABLE IF NOT EXISTS user_platform (
    user_id  BIGINT PRIMARY KEY,
    platform TEXT NOT NULL DEFAULT 'android'
);

CREATE INDEX IF NOT EXISTS idx_user_platform ON user_platform (user_id);

CREATE TABLE IF NOT EXISTS proxies (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT UNIQUE NOT NULL,
    proxy_type TEXT NOT NULL DEFAULT 'http',
    host       TEXT NOT NULL,
    port       INTEGER NOT NULL,
    username   TEXT NOT NULL DEFAULT '',
    password   TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_proxies_user ON proxies (user_id);

-- ==================== AppsFlyer ====================

CREATE TABLE IF NOT EXISTS games_af (
    id           SERIAL PRIMARY KEY,
    name         TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    package      TEXT NOT NULL,
    dev_key      TEXT NOT NULL,
    emoji        TEXT NOT NULL DEFAULT '🎮'
);

CREATE TABLE IF NOT EXISTS events_af (
    id           SERIAL PRIMARY KEY,
    game_id      INTEGER NOT NULL REFERENCES games_af (id) ON DELETE CASCADE,
    event_name   TEXT NOT NULL,
    display_name TEXT NOT NULL,
    event_type   TEXT NOT NULL DEFAULT 'level',
    revenue      REAL,
    level_value  INTEGER,
    UNIQUE (game_id, event_name)
);

CREATE INDEX IF NOT EXISTS idx_events_af_game ON events_af (game_id);

-- ==================== Adjust ====================

CREATE TABLE IF NOT EXISTS games_adj (
    id           SERIAL PRIMARY KEY,
    name         TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    app_token    TEXT NOT NULL,
    emoji        TEXT NOT NULL DEFAULT '🎮'
);

CREATE TABLE IF NOT EXISTS events_adj (
    id           SERIAL PRIMARY KEY,
    game_id      INTEGER NOT NULL REFERENCES games_adj (id) ON DELETE CASCADE,
    event_name   TEXT NOT NULL,
    event_token  TEXT NOT NULL,
    display_name TEXT NOT NULL,
    level_value  INTEGER,
    UNIQUE (game_id, event_name)
);

CREATE INDEX IF NOT EXISTS idx_events_adj_game ON events_adj (game_id);

-- ==================== Singular ====================

CREATE TABLE IF NOT EXISTS games_singular (
    id           SERIAL PRIMARY KEY,
    name         TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    package      TEXT NOT NULL,
    app_key      TEXT NOT NULL,
    emoji        TEXT NOT NULL DEFAULT '🎮'
);

CREATE TABLE IF NOT EXISTS events_singular (
    id           SERIAL PRIMARY KEY,
    game_id      INTEGER NOT NULL REFERENCES games_singular (id) ON DELETE CASCADE,
    event_name   TEXT NOT NULL,
    display_name TEXT NOT NULL,
    event_type   TEXT NOT NULL DEFAULT 'level',
    level_value  INTEGER,
    UNIQUE (game_id, event_name)
);

CREATE INDEX IF NOT EXISTS idx_events_singular_game ON events_singular (game_id);

-- ==================== Farm tasks ====================

CREATE TABLE IF NOT EXISTS farm_tasks (
    id           SERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL,
    task_name    TEXT NOT NULL,
    platform     TEXT NOT NULL,
    game_id      INTEGER NOT NULL,
    game_name    TEXT NOT NULL,
    start_level  INTEGER NOT NULL,
    end_level    INTEGER NOT NULL,
    total_days   INTEGER NOT NULL,
    mode         TEXT NOT NULL DEFAULT 'normal',
    current_day  INTEGER NOT NULL DEFAULT 1,
    current_level INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'running',
    created_date TEXT,
    aifa         TEXT NOT NULL DEFAULT '',
    gaid         TEXT NOT NULL DEFAULT '',
    af_uid       TEXT NOT NULL DEFAULT '',
    gps_adid     TEXT NOT NULL DEFAULT '',
    idfa         TEXT NOT NULL DEFAULT '',
    idfv         TEXT NOT NULL DEFAULT '',
    singular_uid TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_farm_tasks_user   ON farm_tasks (user_id);
CREATE INDEX IF NOT EXISTS idx_farm_tasks_status ON farm_tasks (status);

-- ==================== Subscriptions ====================

CREATE TABLE IF NOT EXISTS subscription_plans (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    duration_days INTEGER NOT NULL,
    price         REAL NOT NULL,
    daily_limit   INTEGER NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id               SERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL,
    plan_id          INTEGER NOT NULL,
    plan_name        TEXT NOT NULL,
    daily_limit      INTEGER NOT NULL,
    daily_used       INTEGER NOT NULL DEFAULT 0,
    last_reset_date  DATE,
    start_date       TIMESTAMP DEFAULT NOW(),
    end_date         TIMESTAMP NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active',
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions (status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_end ON subscriptions (end_date);

-- ==================== Payment Settings ====================

CREATE TABLE IF NOT EXISTS payment_settings (
    method            TEXT PRIMARY KEY,
    display_name      TEXT NOT NULL,
    address           TEXT NOT NULL DEFAULT '',
    instructions      TEXT NOT NULL DEFAULT '',
    binance_api_key   TEXT NOT NULL DEFAULT '',
    binance_api_secret TEXT NOT NULL DEFAULT '',
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at        TIMESTAMP DEFAULT NOW()
);

INSERT INTO payment_settings (method, display_name, address, instructions, is_active) VALUES
    ('usdt', '💎 USDT (TRC20)', '', 'أرسل المبلغ إلى العنوان أعلاه، ثم أدخل رقم العملية.', TRUE),
    ('sham_cash', '💰 شام كاش', '', 'أرسل المبلغ إلى الرقم أعلاه، ثم أرسل صورة إثبات الدفع.', TRUE),
    ('syriatel_cash', '💰 سرياتيل كاش', '', 'أرسل المبلغ إلى الرقم أعلاه، ثم أرسل صورة إثبات الدفع.', TRUE)
ON CONFLICT (method) DO NOTHING;

-- ==================== Payment Requests ====================

CREATE TABLE IF NOT EXISTS payment_requests (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    user_name       TEXT NOT NULL,
    user_username   TEXT NOT NULL,
    plan_id         INTEGER NOT NULL,
    plan_name       TEXT NOT NULL,
    method          TEXT NOT NULL,
    amount          REAL NOT NULL,
    transaction_id  TEXT NOT NULL DEFAULT '',
    proof_file_id   TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    admin_id        BIGINT,
    created_at      TIMESTAMP DEFAULT NOW(),
    processed_at    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_payment_requests_user ON payment_requests (user_id);
CREATE INDEX IF NOT EXISTS idx_payment_requests_status ON payment_requests (status);

-- ==================== Default Plans ====================

INSERT INTO subscription_plans (name, duration_days, price, daily_limit, is_active) VALUES
    ('باقة يومية', 1, 2, 10, TRUE),
    ('باقة أسبوعية', 7, 5, 15, TRUE),
    ('باقة شهرية', 30, 15, 20, TRUE)
ON CONFLICT DO NOTHING;

-- =====================================================
-- Default admin users (change IDs as needed)
-- =====================================================
INSERT INTO users (user_id, username, name, admin, allowed, created_at)
VALUES
    (6075014046, 'admin',  'Admin',  1, 1, NOW()::TEXT),
    (5697155314, 'admin2', 'Admin2', 1, 1, NOW()::TEXT),
    (8114043468, 'admin3', 'Admin3', 1, 1, NOW()::TEXT)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_platform (user_id, platform)
VALUES
    (6075014046, 'android'),
    (5697155314, 'android'),
    (8114043468, 'android')
ON CONFLICT (user_id) DO NOTHING;

-- =====================================================
-- AppsFlyer games seed data
-- =====================================================

INSERT INTO games_af (name, display_name, package, dev_key, emoji) VALUES
('dice_dream',        '🎲 Dice Dreams',         'com.superplaystudios.dicedreams',      'Hn5qYjVA',                            '🎲'),
('domino_dreams',     '🃏 Domino Dreams',        'com.screenshake.dominodreams',          'Hn5qYjVA',                            '🃏'),
('buzzle_chaos',      '🎲 Buzzle Chaos',         'com.global.pnck',                       'ZnhUvonKa6qF9xhgt7GcB',               '🎲'),
('coin_master',       '🎲 Coin Master',          'com.moonactive.coinmaster',             'H3KjoCRVTiVgA',                       '🎲'),
('royal_match',       '👑 Royal Match',          'com.dreamgames.royalmatch',             'B27HnbGEcbWC2',                       '👑'),
('merge_gardens',     '🌺 Merge Gardens',        'com.futureplay.mergematch',             'nr8SibwpF',                           '🌺'),
('highroller_vegas',  '🎲 HIGHROLLER Vegas',     'com.lynxgames.hrv',                     'sSpBC5SKPKE',                         '🎲'),
('rock_n_cash',       '💰 Rock N Cash Casino',   'net.flysher.rockncash',                 'W5VWPj5fbC',                          '💰'),
('coinchef',          '🍳 COINCHEF',             'com.FortuneMine.CuisineMaster',         'im6mgZbZJsHKGVo',                    '🍳'),
('blackjack21',       '🃏 Blackjack 21',         'com.kamagames.blackjack',               'YbczyDZZmXbxwp',                     '🃏'),
('sunshine_island',   '🏝️ Sunshine Island',     'com.newmoonproduction.sunshineisland',  'xLmkQ9bPn4',                          '🏝️'),
('farmville3',        '🌾 Farmville 3',          'com.zynga.FarmVille2CountryEscape',    '438VCP',                               '🌾'),
('disney_solitaire',  '🎲 Disney Solitaire',     'com.superplaystudios.disneysolit',     'Hn5qYjVA',                             '🎲'),
('matching_story',    '🎲 Matching Story',       'com.joycastle.mergematch',              'v2w2tuNC',                            '🎲'),
('nations_of_darkness','🎲 Nations of Darkness', 'com.allstarunion.nod',                  'x8jLmPqR',                            '🎲'),
('hero_wars',         '🎲 Hero Wars',            'com.nexters.herowars',                  'MGPcVAUzD9XqbwAY6q7KMf',             '🎲'),
('zombie_waves',      '🧟 Zombie Waves',         'com.ddup.zombiewaves.zw',               'wiQMRPvGaAYTG',                       '🧟')
ON CONFLICT (name) DO NOTHING;

-- Dice Dream events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'dice_dream';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value) VALUES
        (gid, 'af_kingdom_3_restored',  '🏰 Kingdom 3',  'kingdom', 3),
        (gid, 'af_kingdom_18_restored', '🏰 Kingdom 18', 'kingdom', 18)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Domino Dreams events
DO $$
DECLARE gid INTEGER; area INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'domino_dreams';
    IF gid IS NOT NULL THEN
        FOR area IN 1..15 LOOP
            INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value)
            VALUES (gid, 'af_area_' || area || '_completed', '🗺️ Area ' || area, 'level', area)
            ON CONFLICT DO NOTHING;
        END LOOP;
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, 'af_level_100_completed', '🏆 Level 100', 'level', 100)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Royal Match events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'royal_match';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value) VALUES
        (gid, 'af_level_5_completed',   '⭐ Level 5',   'level', 5),
        (gid, 'af_level_10_completed',  '⭐ Level 10',  'level', 10),
        (gid, 'af_level_25_completed',  '⭐ Level 25',  'level', 25),
        (gid, 'af_level_50_completed',  '⭐ Level 50',  'level', 50),
        (gid, 'af_level_100_completed', '⭐ Level 100', 'level', 100)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Merge Gardens events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'merge_gardens';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, revenue) VALUES
        (gid, 'Incent_Player_Level_Up_2', '⭐ Player Level Up 2', 'level',    NULL),
        (gid, 'Incent_IAP_gems2',          '💎 IAP Gems 2',        'purchase', 0.99)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Rock N Cash events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'rock_n_cash';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value) VALUES
        (gid, 'v3_rnc_level_up_10_S2S', '🎰 Level Up 10', 'level', 10)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Coinchef events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'coinchef';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value) VALUES
        (gid, 'level2_completed', '🍳 Level 2 Completed', 'level', 2)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Blackjack 21 events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'blackjack21';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value) VALUES
        (gid, 'af_level_5_completed',  '⭐ Level 5',  'level', 5),
        (gid, 'af_level_10_completed', '⭐ Level 10', 'level', 10),
        (gid, 'af_level_20_completed', '⭐ Level 20', 'level', 20)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Coin Master events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'coin_master';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value) VALUES
        (gid, 'village_1_complete', '🏠 Village 1 Complete', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Hero Wars events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'hero_wars';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value) VALUES
        (gid, 'af_level_10_completed', '⭐ Level 10', 'level', 10),
        (gid, 'af_level_25_completed', '⭐ Level 25', 'level', 25)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Zombie Waves events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'zombie_waves';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value) VALUES
        (gid, 'af_level_10_completed', '🧟 Level 10', 'level', 10),
        (gid, 'af_level_20_completed', '🧟 Level 20', 'level', 20)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Disney Solitaire events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_af WHERE name = 'disney_solitaire';
    IF gid IS NOT NULL THEN
        INSERT INTO events_af (game_id, event_name, display_name, event_type, level_value) VALUES
        (gid, 'af_level_100_completed', '⭐ Level 100', 'level', 100)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- =====================================================
-- Singular games seed data
-- =====================================================

INSERT INTO games_singular (name, display_name, package, app_key, emoji) VALUES
('animals_coins',    '🦁 Animals & Coins',      'com.innplaylabs.animalkingdomraid',      'myappfree_spa_38e4921',    '🦁'),
('time_master',      '⏰ Time Master',           'com.firefog.timemaster',                 'myappfree_spa_38e4921',    '⏰'),
('beast_go',         '🐉 Beast Go',              'com.ninthart.board.beastgo',             'myappfree_spa_38e4921',    '🐉'),
('coin_fantasy',     '💰 Coin Fantasy',          'com.okvision.coinfantasy',               'myappfree_spa_38e4921',    '💰'),
('dragon_farm',      '🐉 Dragon Farm',           'com.dragon.escape.island.adventure',     'myappfree_spa_38e4921',    '🐉'),
('box_cat_jam',      '🐱 Box Cat Jam',           'com.actionfit.blockcat',                 'actionfit_adc622',         '🐱'),
('idle_soap',        '🧼 Idle Soap ASMR',        'games.midnite.isa',                      'myappfree_spa_38e4921',    '🧼'),
('superheroes_idle', '🦸 Superheroes Idle RPG',  'games.midnite.sid',                      'myappfree_spa_38e4921',    '🦸'),
('survivor_idle',    '🏃 Survivor Idle Run',     'games.midnite.sri',                      'myappfree_spa_38e4921',    '🏃'),
('pop_slots',        '🎰 POP Slots',             'com.playstudios.popslots',               'playstudios_3852f8',       '🎰'),
('mgm_slots',        '🎰 MGM Slots Live',        'com.playstudios.showstar',               'playstudios_3852f8',       '🎰'),
('myvegas',          '🎰 myVEGAS Slots',         'com.playstudios.myvegas',                'playstudios_3852f8',       '🎰'),
('power_spin',       '💪 Power Spin Quest',      'com.braingames.powerquest',              'brain_games_a7dde873',     '💪'),
('sweet_jam',        '🍯 Sweet Jam!',            'puzzle.game.sweetjam',                   'myappfree_spa_38e4921',    '🍯'),
('matching_go',      '🔗 Matching Go!',          'com.matchinggo.puzzlegames',             'xinagyi_f45',              '🔗'),
('screw_out',        '🔧 Screw Out Factory 3D',  'com.ntt.screw.out.factory',              'puzzle_s',                 '🔧'),
('hole_collect',     '🕳️ Hole Collect',          'com.ntt.hole.collect.objects',           'puzzle_s',                 '🕳️'),
('tetris_block',     '🧩 Tetris Block Party',    'com.playstudios.tetrisblockparty',       'playstudios_3852f8',       '🧩'),
('word_madness',     '📖 Word Madness',          'com.word.madness',                       'brain_games_a7dde873',     '📖'),
('word_wise',        '📖 Word Wise',             'com.playx.wordwise.crossword',           'myappfree_spa_38e4921',    '📖'),
('eatventure',       '🍔 Eatventure',            'com.hwqgrhhjfd.idlefastfood',            'lessmore_edff',            '🍔')
ON CONFLICT (name) DO NOTHING;

-- Singular events
DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'animals_coins';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, 'sng_level_achieved', '🦁 sng_level_achieved', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'time_master';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, 'sng_level_achieved', '⏰ sng_level_achieved', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'beast_go';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, 'sng_level_achieved', '🐉 sng_level_achieved', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'idle_soap';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, 'sng_level_achieved', '🧼 sng_level_achieved', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'superheroes_idle';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, 'mn_cheater_level_achieved', '🦸 mn_cheater_level_achieved', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'survivor_idle';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, 'sng_level_achieved', '🏃 sng_level_achieved', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'sweet_jam';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, 'sng_level_achieved', '🍯 sng_level_achieved', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'matching_go';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES
        (gid, 'user_level_complete_1', '🔗 user_level_complete_1', 'level', 1),
        (gid, 'user_level_complete_5', '🔗 user_level_complete_5', 'level', 5)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'hole_collect';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, 'sng_level_achieved', '🕳️ sng_level_achieved', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'word_madness';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES (gid, '_levels_completed', '📖 _levels_completed', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM games_singular WHERE name = 'eatventure';
    IF gid IS NOT NULL THEN
        INSERT INTO events_singular (game_id, event_name, display_name, event_type, level_value)
        VALUES
        (gid, 'restaurant_unlocked',     '🍔 restaurant_unlocked',     'level', 1),
        (gid, 'lm_restaurant_completion','🍔 lm_restaurant_completion', 'level', 1)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;
