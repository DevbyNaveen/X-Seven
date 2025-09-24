-- Evolution API Integration Database Migration
-- This migration adds tables for Evolution API multi-tenant WhatsApp and phone management

-- Create Evolution Instances table
CREATE TABLE IF NOT EXISTS evolution_instances (
    id SERIAL PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    
    -- Instance configuration
    instance_name VARCHAR(255) UNIQUE NOT NULL,
    instance_token VARCHAR(500),
    
    -- Phone number configuration
    phone_number VARCHAR(50),
    phone_country_code VARCHAR(10),
    phone_provider VARCHAR(50),
    phone_sid VARCHAR(255),
    
    -- Instance status
    status VARCHAR(50) DEFAULT 'creating',
    last_seen TIMESTAMP,
    
    -- WhatsApp configuration
    whatsapp_enabled BOOLEAN DEFAULT FALSE,
    whatsapp_status VARCHAR(50) DEFAULT 'disabled',
    whatsapp_qr_code TEXT,
    whatsapp_profile JSONB DEFAULT '{}',
    whatsapp_business_profile JSONB DEFAULT '{}',
    
    -- Evolution API configuration
    evolution_config JSONB DEFAULT '{}',
    webhook_url VARCHAR(500),
    
    -- Usage tracking
    messages_sent INTEGER DEFAULT 0,
    messages_received INTEGER DEFAULT 0,
    calls_handled INTEGER DEFAULT 0,
    last_activity TIMESTAMP,
    
    -- Billing and limits
    monthly_cost DECIMAL(10,2) DEFAULT 0.00,
    usage_limits JSONB DEFAULT '{}',
    current_usage JSONB DEFAULT '{}',
    
    -- Error tracking
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create Evolution Messages table
CREATE TABLE IF NOT EXISTS evolution_messages (
    id SERIAL PRIMARY KEY,
    evolution_instance_id INTEGER NOT NULL REFERENCES evolution_instances(id) ON DELETE CASCADE,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    
    -- Message identification
    message_id VARCHAR(255) NOT NULL,
    whatsapp_message_id VARCHAR(255),
    
    -- Message content
    message_type VARCHAR(50) DEFAULT 'text',
    content TEXT NOT NULL,
    media_url VARCHAR(1000),
    media_type VARCHAR(100),
    
    -- Participants
    from_number VARCHAR(50) NOT NULL,
    to_number VARCHAR(50) NOT NULL,
    contact_name VARCHAR(255),
    
    -- Message status
    direction VARCHAR(20) NOT NULL, -- 'inbound' or 'outbound'
    status VARCHAR(50) DEFAULT 'pending',
    
    -- Timestamps
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    
    -- AI processing
    ai_processed BOOLEAN DEFAULT FALSE,
    ai_response_generated BOOLEAN DEFAULT FALSE,
    ai_response_content TEXT,
    ai_processing_time DECIMAL(8,3),
    
    -- Context and metadata
    conversation_context JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create Evolution Webhook Events table
CREATE TABLE IF NOT EXISTS evolution_webhook_events (
    id SERIAL PRIMARY KEY,
    evolution_instance_id INTEGER REFERENCES evolution_instances(id) ON DELETE CASCADE,
    instance_name VARCHAR(255) NOT NULL,
    
    -- Event details
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB DEFAULT '{}',
    
    -- Processing status
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP,
    processing_error TEXT,
    
    -- Raw webhook data
    raw_payload JSONB DEFAULT '{}',
    headers JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add Evolution API fields to businesses table
ALTER TABLE businesses 
ADD COLUMN IF NOT EXISTS evolution_instance_id INTEGER REFERENCES evolution_instances(id),
ADD COLUMN IF NOT EXISTS evolution_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS evolution_config JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS whatsapp_business_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS phone_config_status VARCHAR(50) DEFAULT 'not_configured';

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_evolution_instances_business_id ON evolution_instances(business_id);
CREATE INDEX IF NOT EXISTS idx_evolution_instances_instance_name ON evolution_instances(instance_name);
CREATE INDEX IF NOT EXISTS idx_evolution_instances_status ON evolution_instances(status);
CREATE INDEX IF NOT EXISTS idx_evolution_instances_phone_number ON evolution_instances(phone_number);

CREATE INDEX IF NOT EXISTS idx_evolution_messages_instance_id ON evolution_messages(evolution_instance_id);
CREATE INDEX IF NOT EXISTS idx_evolution_messages_business_id ON evolution_messages(business_id);
CREATE INDEX IF NOT EXISTS idx_evolution_messages_message_id ON evolution_messages(message_id);
CREATE INDEX IF NOT EXISTS idx_evolution_messages_direction ON evolution_messages(direction);
CREATE INDEX IF NOT EXISTS idx_evolution_messages_ai_processed ON evolution_messages(ai_processed);
CREATE INDEX IF NOT EXISTS idx_evolution_messages_created_at ON evolution_messages(created_at);

CREATE INDEX IF NOT EXISTS idx_evolution_webhook_events_instance_name ON evolution_webhook_events(instance_name);
CREATE INDEX IF NOT EXISTS idx_evolution_webhook_events_event_type ON evolution_webhook_events(event_type);
CREATE INDEX IF NOT EXISTS idx_evolution_webhook_events_processed ON evolution_webhook_events(processed);
CREATE INDEX IF NOT EXISTS idx_evolution_webhook_events_created_at ON evolution_webhook_events(created_at);

-- Create unique constraint for business-instance relationship
CREATE UNIQUE INDEX IF NOT EXISTS idx_evolution_instances_business_unique 
ON evolution_instances(business_id) WHERE status != 'deleted';

-- Create composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_evolution_messages_business_direction_created 
ON evolution_messages(business_id, direction, created_at);

CREATE INDEX IF NOT EXISTS idx_evolution_messages_instance_ai_processing 
ON evolution_messages(evolution_instance_id, ai_processed, created_at);

-- Add triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_evolution_instances_updated_at 
    BEFORE UPDATE ON evolution_instances 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_evolution_messages_updated_at 
    BEFORE UPDATE ON evolution_messages 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_evolution_webhook_events_updated_at 
    BEFORE UPDATE ON evolution_webhook_events 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE evolution_instances IS 'Evolution API instances for multi-tenant WhatsApp and phone management';
COMMENT ON TABLE evolution_messages IS 'All messages sent and received through Evolution API instances';
COMMENT ON TABLE evolution_webhook_events IS 'Webhook events received from Evolution API';

COMMENT ON COLUMN evolution_instances.instance_name IS 'Unique identifier for Evolution API instance (format: business_{business_id})';
COMMENT ON COLUMN evolution_instances.phone_number IS 'Phone number associated with this instance';
COMMENT ON COLUMN evolution_instances.whatsapp_enabled IS 'Whether WhatsApp is enabled for this instance';
COMMENT ON COLUMN evolution_instances.monthly_cost IS 'Monthly cost for this instance in USD';

COMMENT ON COLUMN evolution_messages.direction IS 'Message direction: inbound (from customer) or outbound (to customer)';
COMMENT ON COLUMN evolution_messages.ai_processed IS 'Whether this message has been processed by AI';
COMMENT ON COLUMN evolution_messages.ai_response_generated IS 'Whether AI generated a response to this message';

-- Insert default configuration for existing businesses (optional)
-- This can be run separately if needed to migrate existing businesses
/*
INSERT INTO evolution_instances (business_id, instance_name, status)
SELECT 
    id, 
    'business_' || id::text, 
    'not_configured'
FROM businesses 
WHERE subscription_plan IN ('pro', 'enterprise')
AND NOT EXISTS (
    SELECT 1 FROM evolution_instances ei WHERE ei.business_id = businesses.id
);
*/
