-- Custom Memory Migration for X-SevenAI Database
-- Based on your existing schema analysis
-- Compatible with UUID-based architecture

-- =====================================================
-- ENABLE VECTOR EXTENSION (Required for semantic search)
-- =====================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================
-- CONTEXT MEMORY SYSTEM TABLES
-- =====================================================

-- 1. Conversation Context Memory
-- Compatible with your TEXT session_id from messages table
CREATE TABLE IF NOT EXISTS conversation_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,  -- Matches your messages.session_id type
    user_id UUID,  -- Compatible with your UUID user relationships
    memory_type TEXT NOT NULL, -- 'short_term', 'long_term', 'semantic'
    context_key TEXT NOT NULL,
    context_value JSONB,
    importance_score REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '30 days'),
    UNIQUE(session_id, context_key)
);

-- 2. Business Context Sections
-- Compatible with your businesses.id UUID type
CREATE TABLE IF NOT EXISTS business_context_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,  -- Matches your businesses.id UUID
    section_type TEXT NOT NULL, -- 'menu', 'services', 'hours', 'location', 'policies', 'specials'
    section_name TEXT NOT NULL,
    section_content JSONB,
    section_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(business_id, section_type, section_name)
);

-- 3. Semantic Memory Vectors
-- Compatible with your session_id TEXT type
CREATE TABLE IF NOT EXISTS semantic_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,  -- Matches your messages.session_id
    user_id UUID,  -- Compatible with your UUID system
    content_type TEXT NOT NULL, -- 'conversation', 'business_info', 'user_preference'
    content_text TEXT NOT NULL,
    embedding_vector VECTOR(384), -- Using pgvector for embeddings
    metadata JSONB,
    relevance_score REAL DEFAULT 0.5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Memory Consolidation Log
-- Tracks memory optimization operations
CREATE TABLE IF NOT EXISTS memory_consolidation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,  -- Matches your session_id type
    consolidation_type TEXT NOT NULL, -- 'merge', 'summarize', 'archive', 'forget'
    old_memory_ids UUID[],
    new_memory_id UUID,
    consolidation_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Context Relevance Scores
-- Dynamic relevance scoring system
CREATE TABLE IF NOT EXISTS context_relevance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,  -- Matches your session_id type
    context_type TEXT NOT NULL,
    context_key TEXT NOT NULL,
    relevance_score REAL DEFAULT 0.5,
    decay_factor REAL DEFAULT 0.95,
    last_calculated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(session_id, context_type, context_key)
);

-- 6. User Context Profiles
-- Compatible with your user_id UUID system
CREATE TABLE IF NOT EXISTS user_context_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL,  -- Compatible with your UUID user system
    profile_data JSONB,
    preferences JSONB,
    behavior_patterns JSONB,
    context_history JSONB,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Conversation Memory Indexes
CREATE INDEX IF NOT EXISTS idx_conversation_memory_session ON conversation_memory(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_memory_type ON conversation_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_conversation_memory_expires ON conversation_memory(expires_at);
CREATE INDEX IF NOT EXISTS idx_conversation_memory_importance ON conversation_memory(importance_score DESC);

-- Business Context Sections Indexes
CREATE INDEX IF NOT EXISTS idx_business_sections_business ON business_context_sections(business_id);
CREATE INDEX IF NOT EXISTS idx_business_sections_type ON business_context_sections(section_type);
CREATE INDEX IF NOT EXISTS idx_business_sections_active ON business_context_sections(is_active);

-- Semantic Memory Indexes
CREATE INDEX IF NOT EXISTS idx_semantic_memory_session ON semantic_memory(session_id);
CREATE INDEX IF NOT EXISTS idx_semantic_memory_type ON semantic_memory(content_type);
CREATE INDEX IF NOT EXISTS idx_semantic_memory_vector ON semantic_memory USING ivfflat (embedding_vector vector_cosine_ops);

-- Context Relevance Indexes
CREATE INDEX IF NOT EXISTS idx_context_relevance_session ON context_relevance(session_id);
CREATE INDEX IF NOT EXISTS idx_context_relevance_score ON context_relevance(relevance_score DESC);

-- =====================================================
-- FUNCTIONS AND TRIGGERS
-- =====================================================

-- Function to automatically update last_accessed_at
CREATE OR REPLACE FUNCTION update_memory_access()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversation_memory
    SET access_count = access_count + 1,
        last_accessed_at = NOW()
    WHERE id = NEW.id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for memory access tracking
DROP TRIGGER IF EXISTS trigger_memory_access ON conversation_memory;
CREATE TRIGGER trigger_memory_access
    AFTER UPDATE ON conversation_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_memory_access();

-- Function for memory cleanup (remove expired memories)
CREATE OR REPLACE FUNCTION cleanup_expired_memory()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM conversation_memory
    WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to consolidate memories
-- Compatible with your session_id TEXT type
CREATE OR REPLACE FUNCTION consolidate_session_memories(p_session_id TEXT)
RETURNS UUID AS $$
DECLARE
    new_memory_id UUID;
    memory_count INTEGER;
BEGIN
    -- Count memories for this session
    SELECT COUNT(*) INTO memory_count
    FROM conversation_memory
    WHERE session_id = p_session_id AND memory_type = 'short_term';

    -- If we have enough memories, consolidate them
    IF memory_count >= 5 THEN
        -- Create consolidated memory
        INSERT INTO conversation_memory (
            session_id,
            memory_type,
            context_key,
            context_value,
            importance_score
        )
        SELECT
            p_session_id,
            'long_term',
            'consolidated_context_' || NOW()::TEXT,
            jsonb_build_object(
                'consolidated_at', NOW(),
                'memory_count', memory_count,
                'session_summary', 'Consolidated from multiple short-term memories'
            ),
            0.8
        RETURNING id INTO new_memory_id;

        -- Log consolidation
        INSERT INTO memory_consolidation_log (
            session_id,
            consolidation_type,
            old_memory_ids,
            new_memory_id,
            consolidation_reason
        )
        SELECT
            p_session_id,
            'consolidate',
            array_agg(id),
            new_memory_id,
            'Automatic consolidation of ' || memory_count || ' short-term memories'
        FROM conversation_memory
        WHERE session_id = p_session_id AND memory_type = 'short_term';

        -- Archive old memories
        UPDATE conversation_memory
        SET memory_type = 'archived',
            expires_at = NOW() + INTERVAL '90 days'
        WHERE session_id = p_session_id AND memory_type = 'short_term';

        RETURN new_memory_id;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- INITIAL DATA SEEDING
-- =====================================================

-- Insert some default business context sections for existing businesses
-- Compatible with your businesses.id UUID type
INSERT INTO business_context_sections (business_id, section_type, section_name, section_content, section_order)
SELECT
    b.id,
    'overview',
    'Business Overview',
    jsonb_build_object(
        'name', b.name,
        'category', b.category,
        'description', b.description,
        'is_active', b.is_active,
        'phone', b.phone,
        'email', b.email
    ),
    1
FROM businesses b
WHERE NOT EXISTS (
    SELECT 1 FROM business_context_sections bcs
    WHERE bcs.business_id = b.id AND bcs.section_type = 'overview'
);

-- Insert menu sections for businesses with menu items
-- Compatible with your menu_items.business_id UUID type
INSERT INTO business_context_sections (business_id, section_type, section_name, section_content, section_order)
SELECT
    mi.business_id,
    'menu',
    'Menu Items',
    jsonb_build_object(
        'items', jsonb_agg(
            jsonb_build_object(
                'id', mi.id::text,
                'name', mi.name,
                'description', mi.description,
                'price', mi.price,
                'is_available', mi.is_available,
                'sort_order', mi.sort_order
            )
        ),
        'total_items', COUNT(*)
    ),
    2
FROM menu_items mi
WHERE mi.is_available = true
GROUP BY mi.business_id
ON CONFLICT (business_id, section_type, section_name) DO NOTHING;

-- Insert working hours sections for businesses
INSERT INTO business_context_sections (business_id, section_type, section_name, section_content, section_order)
SELECT
    b.id,
    'hours',
    'Working Hours',
    jsonb_build_object(
        'business_id', b.id,
        'business_name', b.name,
        'note', 'Working hours available in working_hours table'
    ),
    3
FROM businesses b
WHERE EXISTS (
    SELECT 1 FROM working_hours wh WHERE wh.business_id = b.id
)
ON CONFLICT (business_id, section_type, section_name) DO NOTHING;

-- =====================================================
-- VIEWS FOR EASY QUERYING
-- =====================================================

-- View for active business context
CREATE OR REPLACE VIEW active_business_context AS
SELECT
    bcs.*,
    b.name as business_name,
    b.category as business_category
FROM business_context_sections bcs
JOIN businesses b ON bcs.business_id = b.id
WHERE bcs.is_active = true AND b.is_active = true
ORDER BY bcs.business_id, bcs.section_order;

-- View for session memory summary
CREATE OR REPLACE VIEW session_memory_summary AS
SELECT
    session_id,
    memory_type,
    COUNT(*) as memory_count,
    AVG(importance_score) as avg_importance,
    MAX(last_accessed_at) as last_access,
    SUM(access_count) as total_accesses
FROM conversation_memory
GROUP BY session_id, memory_type;

-- View for business memory overview
CREATE OR REPLACE VIEW business_memory_overview AS
SELECT
    b.id as business_id,
    b.name as business_name,
    b.category as business_category,
    COUNT(bcs.id) as context_sections,
    COUNT(DISTINCT sm.id) as semantic_memories,
    MAX(bcs.last_updated) as last_context_update
FROM businesses b
LEFT JOIN business_context_sections bcs ON b.id = bcs.business_id AND bcs.is_active = true
LEFT JOIN semantic_memory sm ON sm.user_id = b.user_id
GROUP BY b.id, b.name, b.category;

-- =====================================================
-- RLS POLICIES (Row Level Security)
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE conversation_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_context_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE semantic_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_consolidation_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE context_relevance ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_context_profiles ENABLE ROW LEVEL SECURITY;

-- Note: Add your specific RLS policies based on your authentication setup
-- Example policy for conversation_memory (adjust based on your auth):
-- CREATE POLICY "Users can access their own session memories" ON conversation_memory
-- FOR ALL USING (auth.uid()::text = session_id OR user_id = auth.uid());

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE 'X-SevenAI Advanced Memory System Migration Completed Successfully!';
    RAISE NOTICE 'Created tables: conversation_memory, business_context_sections, semantic_memory';
    RAISE NOTICE 'Created supporting tables: memory_consolidation_log, context_relevance, user_context_profiles';
    RAISE NOTICE 'Created indexes and functions for memory management';
    RAISE NOTICE 'Seeded initial business context sections';
    RAISE NOTICE 'Migration is compatible with your existing UUID-based database schema';
END $$;
