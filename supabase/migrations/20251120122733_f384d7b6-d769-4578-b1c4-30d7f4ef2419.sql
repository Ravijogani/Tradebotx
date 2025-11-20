-- Recreate the trigger that updates strategy_performance when trades change
DROP TRIGGER IF EXISTS update_strategy_performance_trigger ON trades;

CREATE TRIGGER update_strategy_performance_trigger
  AFTER INSERT OR UPDATE OR DELETE ON trades
  FOR EACH ROW
  EXECUTE FUNCTION update_strategy_performance();

-- Force trigger execution by updating closed trades
-- This will recalculate all statistics for existing trades
UPDATE trades 
SET metadata = metadata 
WHERE status = 'closed';