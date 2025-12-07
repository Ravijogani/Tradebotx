-- Insert Logic Gate Blocks
INSERT INTO strategy_blocks (block_type, name, description, category, icon, config_schema, default_config, is_premium, is_active) VALUES
('and_gate', 'AND Gate', 'All connected conditions must be true', 'logic', 'GitMerge', '{"inputs":{"type":"array","min":2,"max":5}}', '{"inputs":2}', false, true),
('or_gate', 'OR Gate', 'At least one connected condition must be true', 'logic', 'GitBranch', '{"inputs":{"type":"array","min":2,"max":5}}', '{"inputs":2}', false, true),
('not_gate', 'NOT Gate', 'Inverts the condition result', 'logic', 'RotateCcw', '{}', '{}', false, true),
('xor_gate', 'XOR Gate', 'Exactly one condition must be true', 'logic', 'Shuffle', '{"inputs":{"type":"array","min":2,"max":5}}', '{"inputs":2}', true, true),
('delay', 'Delay Block', 'Wait for specified time before proceeding', 'logic', 'Clock', '{"delay_seconds":{"type":"number","min":1,"max":3600}}', '{"delay_seconds":60}', false, true),
('loop', 'Loop Block', 'Repeat actions for specified iterations', 'logic', 'RefreshCw', '{"iterations":{"type":"number","min":1,"max":100},"interval_seconds":{"type":"number","min":1,"max":3600}}', '{"iterations":5,"interval_seconds":60}', true, true);

-- Insert AI-Powered Blocks
INSERT INTO strategy_blocks (block_type, name, description, category, icon, config_schema, default_config, is_premium, is_active) VALUES
('pattern_recognition', 'Pattern Recognition', 'AI-powered chart pattern detection', 'ai', 'Eye', '{"patterns":{"type":"array","options":["head_shoulders","double_top","double_bottom","triangle","wedge","flag"]},"confidence_threshold":{"type":"number","min":0.5,"max":1}}', '{"patterns":["head_shoulders","double_top"],"confidence_threshold":0.75}', true, true),
('sentiment_analyzer', 'Sentiment Analyzer', 'Analyze market sentiment from news and social media', 'ai', 'MessageCircle', '{"sources":{"type":"array","options":["news","twitter","reddit"]},"sentiment_threshold":{"type":"number","min":-1,"max":1}}', '{"sources":["news"],"sentiment_threshold":0.3}', true, true),
('trend_predictor', 'Trend Predictor', 'ML-based trend direction prediction', 'ai', 'TrendingUp', '{"timeframe":{"type":"select","options":["5m","15m","1h","4h","1d"]},"lookback_periods":{"type":"number","min":10,"max":200}}', '{"timeframe":"1h","lookback_periods":50}', true, true),
('volatility_forecast', 'Volatility Forecast', 'Predict upcoming volatility changes', 'ai', 'Activity', '{"forecast_periods":{"type":"number","min":1,"max":24},"volatility_threshold":{"type":"number","min":0,"max":100}}', '{"forecast_periods":6,"volatility_threshold":25}', true, true);

-- Insert Portfolio Blocks
INSERT INTO strategy_blocks (block_type, name, description, category, icon, config_schema, default_config, is_premium, is_active) VALUES
('correlation_filter', 'Correlation Filter', 'Filter trades based on symbol correlation', 'portfolio', 'Link', '{"max_correlation":{"type":"number","min":0,"max":1},"lookback_days":{"type":"number","min":5,"max":90}}', '{"max_correlation":0.7,"lookback_days":30}', true, true),
('exposure_limit', 'Exposure Limit', 'Limit overall portfolio exposure', 'portfolio', 'Shield', '{"max_exposure_percent":{"type":"number","min":1,"max":100},"per_symbol_max":{"type":"number","min":1,"max":50}}', '{"max_exposure_percent":50,"per_symbol_max":20}', true, true),
('multi_symbol', 'Multi-Symbol Scanner', 'Scan and trade multiple symbols simultaneously', 'portfolio', 'Layers', '{"symbols":{"type":"array"},"max_concurrent":{"type":"number","min":1,"max":10}}', '{"symbols":["EURUSD","GBPUSD","USDJPY"],"max_concurrent":3}', true, true),
('hedge_position', 'Hedge Position', 'Automatically create hedging positions', 'portfolio', 'RefreshCcw', '{"hedge_ratio":{"type":"number","min":0.1,"max":1},"hedge_symbol":{"type":"string"}}', '{"hedge_ratio":0.5,"hedge_symbol":""}', true, true);

-- Insert additional indicator blocks
INSERT INTO strategy_blocks (block_type, name, description, category, icon, config_schema, default_config, is_premium, is_active) VALUES
('bollinger_bands', 'Bollinger Bands', 'Price bands based on standard deviation', 'indicator', 'Activity', '{"period":{"type":"number","min":5,"max":50},"deviation":{"type":"number","min":1,"max":4}}', '{"period":20,"deviation":2}', false, true),
('atr', 'ATR', 'Average True Range volatility indicator', 'indicator', 'BarChart', '{"period":{"type":"number","min":5,"max":50}}', '{"period":14}', false, true),
('stochastic', 'Stochastic', 'Stochastic oscillator for overbought/oversold', 'indicator', 'Percent', '{"k_period":{"type":"number","min":5,"max":21},"d_period":{"type":"number","min":3,"max":9}}', '{"k_period":14,"d_period":3}', false, true)
ON CONFLICT DO NOTHING;