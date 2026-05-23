-- Example data import using the reusable upsert_knowledge_chunk function.
-- Keep business data here. Keep insert/upsert rules in 003_create_knowledge_chunk_upsert.sql.

SELECT upsert_knowledge_chunk(
    p_source_doc_id := 'loan_faq_v1',
    p_source_name := 'Loan product FAQ',
    p_source_type := 'markdown',
    p_chunk_index := 0,
    p_chunk_text := '初始额度不高，主要是因为平台需要控制欺诈风险。当前市场中虚假资料、恶意借款等情况较多，所以系统会先根据用户资料、还款记录和风险策略给出较保守的额度。',
    p_embedding := NULL,
    p_metadata := '{"category":"faq","user_level":"all","version":"v1","topic":"credit_limit"}'::jsonb,
    p_language := 'zh-CN',
    p_user_level := 'all',
    p_tags := ARRAY['faq', 'loan', 'credit_limit'],
    p_token_count := 96
);

SELECT upsert_knowledge_chunk(
    p_source_doc_id := 'loan_faq_v1',
    p_source_name := 'Loan product FAQ',
    p_source_type := 'markdown',
    p_chunk_index := 1,
    p_chunk_text := '对于信用记录良好、能够按时还款的用户，系统会逐步提高信任等级。通常在第三次按时还款之后，额度会有明显提升，利率也可能同步降低。',
    p_embedding := NULL,
    p_metadata := '{"category":"faq","user_level":"all","version":"v1","topic":"repayment"}'::jsonb,
    p_language := 'zh-CN',
    p_user_level := 'all',
    p_tags := ARRAY['faq', 'loan', 'repayment'],
    p_token_count := 72
);

-- Example with a real embedding vector:
-- SELECT upsert_knowledge_chunk(
--     p_source_doc_id := 'loan_faq_v1',
--     p_source_name := 'Loan product FAQ',
--     p_chunk_index := 0,
--     p_chunk_text := '初始额度不高，主要是因为平台需要控制欺诈风险。',
--     p_embedding := '[0.012, -0.034, 0.056]'::vector,
--     p_metadata := '{"category":"faq","user_level":"all"}'::jsonb
-- );
