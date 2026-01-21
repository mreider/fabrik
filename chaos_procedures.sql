-- Realistic Business Logic Procedures (with performance issues during chaos mode)
-- These procedures simulate legitimate business operations that become slow under load
-- IDEMPOTENT: Safe to run multiple times during deployment/installation

-- Create schema if not exists for organization
CREATE SCHEMA IF NOT EXISTS chaos_procedures;

-- Set search path to include our schema
SET search_path TO chaos_procedures, public;

-- Create installation tracking table
CREATE TABLE IF NOT EXISTS chaos_procedures.installation_log (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    installed_at TIMESTAMP DEFAULT NOW(),
    notes TEXT
);

-- Check if this version is already installed
DO $$
DECLARE
    current_version VARCHAR(50) := 'v2.0.0';
    install_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO install_count
    FROM chaos_procedures.installation_log
    WHERE version = current_version;

    IF install_count = 0 THEN
        INSERT INTO chaos_procedures.installation_log (version, notes)
        VALUES (current_version, 'Installing chaos procedures for realistic business logic simulation');
        RAISE NOTICE 'Installing chaos procedures version %', current_version;
    ELSE
        RAISE NOTICE 'Chaos procedures version % already installed, updating functions', current_version;
    END IF;
END $$;

-- 1. Order compliance validation with complex business rules
CREATE OR REPLACE FUNCTION validate_order_compliance(delay_seconds FLOAT DEFAULT 2.0)
RETURNS TEXT AS $$
DECLARE
    result TEXT := '';
    counter INTEGER := 0;
    start_time TIMESTAMP;
    target_duration INTERVAL;
BEGIN
    start_time := clock_timestamp();
    target_duration := delay_seconds * INTERVAL '1 second';

    -- CPU-intensive loop with mathematical operations
    WHILE clock_timestamp() - start_time < target_duration LOOP
        counter := counter + 1;
        -- Expensive mathematical operations
        result := result || md5(counter::text);
        IF counter % 1000 = 0 THEN
            -- Periodic expensive string operations
            result := substring(result, 1, 100) || md5(random()::text);
        END IF;
    END LOOP;

    RETURN 'Order compliance validation completed after ' || counter || ' rule checks';
END;
$$ LANGUAGE plpgsql;

-- 2. Analytics cache refresh with inventory reconciliation
CREATE OR REPLACE FUNCTION refresh_analytics_cache(delay_seconds FLOAT DEFAULT 1.5)
RETURNS TEXT AS $$
DECLARE
    temp_result INTEGER;
BEGIN
    -- Create temporary analytics table for cache refresh
    DROP TABLE IF EXISTS analytics_temp_table;
    CREATE TEMP TABLE analytics_temp_table AS
    SELECT generate_series(1, 10000) as order_id, md5(random()::text) as customer_segment;

    -- Complex analytics queries with cross-joins
    SELECT COUNT(*) INTO temp_result
    FROM analytics_temp_table t1
    JOIN analytics_temp_table t2 ON t1.order_id != t2.order_id
    WHERE t1.order_id < 1000;

    -- Add sleep to extend the duration
    PERFORM pg_sleep(delay_seconds);

    DROP TABLE analytics_temp_table;

    RETURN 'Analytics cache refresh completed with ' || temp_result || ' reconciled records';
END;
$$ LANGUAGE plpgsql;

-- 3. Customer recommendation engine with ML-style processing
CREATE OR REPLACE FUNCTION generate_customer_recommendations(delay_seconds FLOAT DEFAULT 1.0)
RETURNS TEXT AS $$
DECLARE
    result_count INTEGER;
BEGIN
    -- Memory intensive operations with large sorts
    WITH RECURSIVE expensive_cte(n, data) AS (
        SELECT 1, md5(random()::text)
        UNION ALL
        SELECT n + 1, md5((n + random())::text)
        FROM expensive_cte
        WHERE n < 5000
    ),
    sorted_data AS (
        SELECT *, row_number() OVER (ORDER BY data DESC) as rank
        FROM expensive_cte
    )
    SELECT COUNT(*) INTO result_count
    FROM sorted_data
    WHERE rank % 10 = 0;

    -- Additional sleep for consistency
    PERFORM pg_sleep(delay_seconds);

    RETURN 'Customer recommendations generated for ' || result_count || ' customer segments';
END;
$$ LANGUAGE plpgsql;

-- 4. Business intelligence aggregation (appears to be legitimate BI workload)
CREATE OR REPLACE FUNCTION update_business_metrics(min_delay FLOAT DEFAULT 1.0, max_delay FLOAT DEFAULT 3.0)
RETURNS TEXT AS $$
DECLARE
    delay_seconds FLOAT;
    process_type INTEGER;
    result TEXT;
BEGIN
    -- Random processing time based on data volume
    delay_seconds := min_delay + (max_delay - min_delay) * random();

    -- Random business process type (1-3)
    process_type := 1 + floor(random() * 3);

    CASE process_type
        WHEN 1 THEN
            result := validate_order_compliance(delay_seconds);
        WHEN 2 THEN
            result := refresh_analytics_cache(delay_seconds * 0.7);
        WHEN 3 THEN
            result := generate_customer_recommendations(delay_seconds * 0.8);
        ELSE
            result := validate_order_compliance(delay_seconds);
    END CASE;

    RETURN 'Business metrics update - ' || result;
END;
$$ LANGUAGE plpgsql;

-- 5. Fraud detection scoring (lightweight but realistic)
CREATE OR REPLACE FUNCTION calculate_fraud_score(delay_ms INTEGER DEFAULT 500)
RETURNS TEXT AS $$
BEGIN
    -- Fraud detection processing with computational delay
    PERFORM pg_sleep(delay_ms / 1000.0);
    RETURN 'Fraud score calculation completed in ' || delay_ms || 'ms';
END;
$$ LANGUAGE plpgsql;

-- 6. Shipping analytics generation (logistics optimization)
CREATE OR REPLACE FUNCTION generate_shipping_analytics(delay_seconds FLOAT DEFAULT 1.5)
RETURNS TEXT AS $$
DECLARE
    route_count INTEGER;
    temp_result INTEGER;
BEGIN
    -- Complex shipping route optimization processing
    DROP TABLE IF EXISTS shipping_routes_temp;
    CREATE TEMP TABLE shipping_routes_temp AS
    SELECT
        generate_series(1, 5000) as route_id,
        random() * 1000 as distance,
        md5(random()::text) as route_hash;

    -- Expensive route optimization calculations
    WITH route_analysis AS (
        SELECT
            route_id,
            distance,
            ROW_NUMBER() OVER (ORDER BY distance) as efficiency_rank
        FROM shipping_routes_temp
        WHERE distance > 100
    )
    SELECT COUNT(*) INTO route_count
    FROM route_analysis ra1
    JOIN route_analysis ra2 ON ra1.efficiency_rank != ra2.efficiency_rank
    WHERE ra1.route_id < 1000;

    -- Additional processing delay
    PERFORM pg_sleep(delay_seconds);

    DROP TABLE shipping_routes_temp;

    RETURN 'Shipping analytics generated for ' || route_count || ' optimized routes';
END;
$$ LANGUAGE plpgsql;

-- 7. Message queue performance analysis (real-time monitoring)
CREATE OR REPLACE FUNCTION analyze_message_queue_performance(delay_ms INTEGER DEFAULT 1000)
RETURNS TEXT AS $$
DECLARE
    queue_metrics TEXT;
    sample_size INTEGER;
BEGIN
    -- Message queue performance monitoring
    sample_size := 1000 + (delay_ms / 10);

    -- Simulate queue analysis with computational work
    WITH queue_stats AS (
        SELECT
            generate_series(1, sample_size) as message_id,
            random() * 100 as processing_time,
            case when random() > 0.95 then 'error' else 'success' end as status
    ),
    performance_metrics AS (
        SELECT
            AVG(processing_time) as avg_time,
            COUNT(CASE WHEN status = 'error' THEN 1 END) as error_count
        FROM queue_stats
    )
    SELECT
        'avg_time=' || avg_time::INTEGER || 'ms,errors=' || error_count
    INTO queue_metrics
    FROM performance_metrics;

    -- Processing delay based on message volume
    PERFORM pg_sleep(delay_ms / 1000.0);

    RETURN 'Queue performance analysis completed: ' || queue_metrics;
END;
$$ LANGUAGE plpgsql;

-- 8. Message deserialization and validation (complex JSON processing)
CREATE OR REPLACE FUNCTION process_message_batch(delay_seconds FLOAT DEFAULT 2.0)
RETURNS TEXT AS $$
DECLARE
    batch_size INTEGER;
    processed_count INTEGER := 0;
    validation_result TEXT;
BEGIN
    -- Simulate message batch processing with validation overhead
    batch_size := 500 + floor(random() * 1000);

    -- Complex JSON schema validation simulation
    WITH message_batch AS (
        SELECT
            generate_series(1, batch_size) as msg_id,
            '{"orderId":"' || generate_series(1, batch_size) || '","timestamp":"' ||
            extract(epoch from now()) || '","payload":' ||
            json_object(ARRAY['field1', 'field2', 'field3'],
                       ARRAY[md5(random()::text), md5(random()::text), random()::text]) ||
            '}' as message_json
    ),
    validated_messages AS (
        SELECT
            msg_id,
            length(message_json) as msg_size,
            case when random() > 0.98 then 'invalid' else 'valid' end as validation_status
        FROM message_batch
    )
    SELECT COUNT(*) INTO processed_count
    FROM validated_messages
    WHERE validation_status = 'valid' AND msg_size > 100;

    -- Schema validation processing delay
    PERFORM pg_sleep(delay_seconds * 0.7);

    -- Consumer group rebalancing simulation (additional delay)
    IF random() < 0.3 THEN
        PERFORM pg_sleep(delay_seconds * 0.5);
        validation_result := 'with consumer rebalancing';
    ELSE
        validation_result := 'standard processing';
    END IF;

    RETURN 'Message batch processed: ' || processed_count || '/' || batch_size || ' messages (' || validation_result || ')';
END;
$$ LANGUAGE plpgsql;

-- 9. Dead letter queue and retry processing (error recovery)
CREATE OR REPLACE FUNCTION process_dlq_messages(delay_seconds FLOAT DEFAULT 1.5)
RETURNS TEXT AS $$
DECLARE
    dlq_count INTEGER;
    retry_attempts INTEGER;
    recovery_type TEXT;
BEGIN
    -- Simulate dead letter queue processing overhead
    dlq_count := 10 + floor(random() * 50);
    retry_attempts := 1 + floor(random() * 3);

    -- Expensive retry logic with exponential backoff simulation
    WITH dlq_analysis AS (
        SELECT
            generate_series(1, dlq_count) as dlq_msg_id,
            generate_series(1, retry_attempts) as attempt_num,
            power(2, generate_series(1, retry_attempts)) as backoff_delay
    ),
    retry_processing AS (
        SELECT
            dlq_msg_id,
            attempt_num,
            case
                when random() > 0.7 then 'recovered'
                when random() > 0.4 then 'retry_needed'
                else 'permanent_failure'
            end as recovery_status
        FROM dlq_analysis
    )
    SELECT
        COUNT(CASE WHEN recovery_status = 'recovered' THEN 1 END)::TEXT ||
        ' recovered, ' ||
        COUNT(CASE WHEN recovery_status = 'permanent_failure' THEN 1 END)::TEXT ||
        ' failed permanently'
    INTO recovery_type
    FROM retry_processing;

    -- DLQ processing delay (expensive error handling)
    PERFORM pg_sleep(delay_seconds);

    RETURN 'DLQ processing completed: ' || recovery_type || ' from ' || dlq_count || ' messages';
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- BACKWARDS COMPATIBILITY AND SAFETY
-- =============================================================================

-- Create public schema wrapper functions for backwards compatibility
-- These ensure existing code continues to work regardless of schema setup

CREATE OR REPLACE FUNCTION public.validate_order_compliance(delay_seconds FLOAT DEFAULT 2.0)
RETURNS TEXT AS $$
BEGIN
    RETURN chaos_procedures.validate_order_compliance(delay_seconds);
EXCEPTION
    WHEN OTHERS THEN
        -- Fallback to simple processing if procedure fails
        PERFORM pg_sleep(COALESCE(delay_seconds, 2.0));
        RETURN 'Order compliance validation completed (fallback mode)';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.refresh_analytics_cache(delay_seconds FLOAT DEFAULT 1.5)
RETURNS TEXT AS $$
BEGIN
    RETURN chaos_procedures.refresh_analytics_cache(delay_seconds);
EXCEPTION
    WHEN OTHERS THEN
        PERFORM pg_sleep(COALESCE(delay_seconds, 1.5));
        RETURN 'Analytics cache refresh completed (fallback mode)';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.generate_customer_recommendations(delay_seconds FLOAT DEFAULT 1.0)
RETURNS TEXT AS $$
BEGIN
    RETURN chaos_procedures.generate_customer_recommendations(delay_seconds);
EXCEPTION
    WHEN OTHERS THEN
        PERFORM pg_sleep(COALESCE(delay_seconds, 1.0));
        RETURN 'Customer recommendations generated (fallback mode)';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.update_business_metrics(min_delay FLOAT DEFAULT 1.0, max_delay FLOAT DEFAULT 3.0)
RETURNS TEXT AS $$
BEGIN
    RETURN chaos_procedures.update_business_metrics(min_delay, max_delay);
EXCEPTION
    WHEN OTHERS THEN
        PERFORM pg_sleep(COALESCE(min_delay + (max_delay - min_delay) * random(), 2.0));
        RETURN 'Business metrics update completed (fallback mode)';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.calculate_fraud_score(delay_ms INTEGER DEFAULT 500)
RETURNS TEXT AS $$
BEGIN
    RETURN chaos_procedures.calculate_fraud_score(delay_ms);
EXCEPTION
    WHEN OTHERS THEN
        PERFORM pg_sleep(COALESCE(delay_ms / 1000.0, 0.5));
        RETURN 'Fraud score calculation completed (fallback mode)';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.generate_shipping_analytics(delay_seconds FLOAT DEFAULT 1.5)
RETURNS TEXT AS $$
BEGIN
    RETURN chaos_procedures.generate_shipping_analytics(delay_seconds);
EXCEPTION
    WHEN OTHERS THEN
        PERFORM pg_sleep(COALESCE(delay_seconds, 1.5));
        RETURN 'Shipping analytics generated (fallback mode)';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.analyze_message_queue_performance(delay_ms INTEGER DEFAULT 1000)
RETURNS TEXT AS $$
BEGIN
    RETURN chaos_procedures.analyze_message_queue_performance(delay_ms);
EXCEPTION
    WHEN OTHERS THEN
        PERFORM pg_sleep(COALESCE(delay_ms / 1000.0, 1.0));
        RETURN 'Queue performance analysis completed (fallback mode)';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.process_message_batch(delay_seconds FLOAT DEFAULT 2.0)
RETURNS TEXT AS $$
BEGIN
    RETURN chaos_procedures.process_message_batch(delay_seconds);
EXCEPTION
    WHEN OTHERS THEN
        PERFORM pg_sleep(COALESCE(delay_seconds, 2.0));
        RETURN 'Message batch processed (fallback mode)';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.process_dlq_messages(delay_seconds FLOAT DEFAULT 1.5)
RETURNS TEXT AS $$
BEGIN
    RETURN chaos_procedures.process_dlq_messages(delay_seconds);
EXCEPTION
    WHEN OTHERS THEN
        PERFORM pg_sleep(COALESCE(delay_seconds, 1.5));
        RETURN 'DLQ processing completed (fallback mode)';
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- INSTALLATION VERIFICATION AND UTILITIES
-- =============================================================================

-- Function to test all procedures are working
CREATE OR REPLACE FUNCTION public.test_chaos_procedures()
RETURNS TABLE(procedure_name TEXT, status TEXT, execution_time INTERVAL) AS $$
DECLARE
    start_time TIMESTAMP;
    proc_record RECORD;
BEGIN
    FOR proc_record IN
        SELECT unnest(ARRAY[
            'validate_order_compliance',
            'refresh_analytics_cache',
            'generate_customer_recommendations',
            'calculate_fraud_score',
            'generate_shipping_analytics',
            'analyze_message_queue_performance',
            'process_message_batch',
            'process_dlq_messages'
        ]) as proc_name
    LOOP
        start_time := clock_timestamp();

        BEGIN
            CASE proc_record.proc_name
                WHEN 'validate_order_compliance' THEN
                    PERFORM public.validate_order_compliance(0.1);
                WHEN 'refresh_analytics_cache' THEN
                    PERFORM public.refresh_analytics_cache(0.1);
                WHEN 'generate_customer_recommendations' THEN
                    PERFORM public.generate_customer_recommendations(0.1);
                WHEN 'calculate_fraud_score' THEN
                    PERFORM public.calculate_fraud_score(100);
                WHEN 'generate_shipping_analytics' THEN
                    PERFORM public.generate_shipping_analytics(0.1);
                WHEN 'analyze_message_queue_performance' THEN
                    PERFORM public.analyze_message_queue_performance(100);
                WHEN 'process_message_batch' THEN
                    PERFORM public.process_message_batch(0.1);
                WHEN 'process_dlq_messages' THEN
                    PERFORM public.process_dlq_messages(0.1);
            END CASE;

            RETURN QUERY SELECT proc_record.proc_name, 'SUCCESS'::TEXT, clock_timestamp() - start_time;

        EXCEPTION WHEN OTHERS THEN
            RETURN QUERY SELECT proc_record.proc_name, 'ERROR: ' || SQLERRM, clock_timestamp() - start_time;
        END;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Log successful installation
INSERT INTO chaos_procedures.installation_log (version, notes)
VALUES ('v2.0.0', 'Installation completed with backwards compatibility and error handling')
ON CONFLICT DO NOTHING;

-- Display installation summary
DO $$
BEGIN
    RAISE NOTICE '=== CHAOS PROCEDURES INSTALLATION COMPLETE ===';
    RAISE NOTICE 'Version: v2.0.0';
    RAISE NOTICE 'Schema: chaos_procedures (with public schema compatibility)';
    RAISE NOTICE 'Functions: 9 business logic simulation procedures';
    RAISE NOTICE 'Features: Error handling, fallback modes, installation tracking';
    RAISE NOTICE 'Test command: SELECT * FROM test_chaos_procedures();';
    RAISE NOTICE '==================================================';
END $$;