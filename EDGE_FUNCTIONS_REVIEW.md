# Edge Functions Comprehensive Review & Improvements

## 📋 Current Edge Functions Analysis

### ✅ **Working Well**

#### 1. **admin-ai-insights** ✓ FIXED
- ✅ Generates AI-powered admin insights
- ✅ Fixed join queries
- ✅ Fixed bot errors query (now uses bot_heartbeats)
- **Status**: Production ready

#### 2. **generate-ai-insights** ✓ FIXED
- ✅ User-facing AI analysis
- ✅ Removed temperature parameter
- ✅ Added tool calling for structured output
- ✅ Added data validation
- ✅ Better error handling
- **Status**: Production ready

#### 3. **send-telegram-notification** ✓ GOOD
- ✅ Sends Telegram notifications
- ✅ Proper error handling
- **Improvement**: Add message templates for consistency

#### 4. **verify-razorpay-payment** ✓ GOOD
- ✅ Payment verification working
- **Improvement**: Add webhook retry mechanism

#### 5. **encrypt-password** ✓ GOOD
- ✅ Secure password encryption
- **Improvement**: Consider key rotation support

### 🟡 **Needs Improvements**

#### 6. **trigger-bot** 🟡
**Issues Found**:
- Falls back to database queue when HTTP fails
- MT5 password decryption errors (legacy plain text handling)

**Improvements Needed**:
```typescript
// 1. Better error handling for bot manager communication
// 2. Remove legacy plain text password support
// 3. Add retry mechanism with exponential backoff
// 4. Better logging for debugging
// 5. Add health check before triggering

// Example improvement:
async function triggerBotWithRetry(config: any, maxRetries = 3) {
  let lastError;
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await triggerBot(config);
    } catch (error) {
      lastError = error;
      if (i < maxRetries - 1) {
        await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i)));
      }
    }
  }
  throw lastError;
}
```

#### 7. **start-trading-bot** 🟡
**Improvements Needed**:
- Add pre-flight checks (MT5 connection, balance, etc.)
- Implement rate limiting per user
- Add bot startup validation
- Better error messages for users

#### 8. **stop-trading-bot** 🟡
**Improvements Needed**:
- Add graceful shutdown with position closing
- Verify all positions closed before stopping
- Send final performance report
- Add force-stop option for emergencies

#### 9. **check-trial-expiry** ✓ FIXED BUT CAN IMPROVE
**Fixed**: Corrected join queries
**Improvements Needed**:
- Add more notification intervals (24h, 12h, 1h before expiry)
- Include upgrade CTA in notifications
- Track notification open rates
- A/B test messaging

### 🔴 **Missing Important Functions**

#### 10. **bot-health-monitor** 🔴 MISSING
**Purpose**: Monitor all running bots and auto-restart failed ones
```typescript
// Suggested implementation
export async function monitorBotHealth() {
  // Check bot heartbeats
  // Find stale/crashed bots
  // Auto-restart with alerts
  // Update bot_heartbeats status
}
```

#### 11. **performance-calculator** 🔴 MISSING
**Purpose**: Real-time performance calculations
```typescript
// Calculate and update:
// - Win rate
// - Sharpe ratio
// - Max drawdown
// - Risk-adjusted returns
// - Compare with benchmarks
```

#### 12. **trade-analyzer** 🔴 MISSING
**Purpose**: Deep analysis of individual trades
```typescript
// Analyze:
// - Entry timing quality
// - Exit timing quality
// - Risk:reward actual vs planned
// - Slippage analysis
// - Commission impact
```

#### 13. **alert-manager** 🔴 MISSING
**Purpose**: Centralized alert system
```typescript
// Manage alerts for:
// - Price levels
// - Profit targets reached
// - Loss limits hit
// - News events
// - System issues
```

#### 14. **backup-manager** 🔴 MISSING
**Purpose**: Automated data backups
```typescript
// Backup:
// - User strategies
// - Trade history
// - Settings
// - Performance data
// Restore on request
```

## 🎯 Priority Improvements

### Immediate (This Week)

1. **Add bot-health-monitor**
   ```typescript
   // Run every 5 minutes
   // Check all active bots
   // Auto-restart crashed bots
   // Alert admins of issues
   ```

2. **Improve trigger-bot reliability**
   - Remove legacy password handling
   - Add retry logic
   - Better error messages

3. **Add rate limiting middleware**
   ```typescript
   // Protect all functions
   const rateLimits = {
     'generate-ai-insights': { requests: 10, window: 3600 },
     'start-trading-bot': { requests: 5, window: 300 },
     'stop-trading-bot': { requests: 10, window: 300 }
   };
   ```

### Short Term (This Month)

4. **Create trade-analyzer function**
   - Analyze completed trades
   - Generate improvement suggestions
   - Feed data to AI insights

5. **Implement alert-manager**
   - Price alerts
   - Profit/loss alerts
   - System alerts
   - Custom user alerts

6. **Add performance-calculator**
   - Real-time metrics
   - Historical comparison
   - Benchmark against indices

### Medium Term (This Quarter)

7. **Webhook system for integrations**
   ```typescript
   // Allow external apps to:
   // - Receive trade notifications
   // - Get bot status updates
   // - Access performance data
   ```

8. **Batch processing system**
   ```typescript
   // Process multiple operations:
   // - Bulk trade imports
   // - Batch user operations
   // - Mass notifications
   ```

9. **Caching layer**
   ```typescript
   // Cache frequently accessed:
   // - User settings
   // - Strategy data
   // - Performance metrics
   // TTL: 5-60 minutes
   ```

## 🔧 Technical Improvements Needed

### 1. **Error Handling Standardization**
```typescript
// Create shared error handler
// supabase/functions/_shared/error-handler-v2.ts
export class AppError extends Error {
  constructor(
    public code: string,
    message: string,
    public statusCode: number = 500,
    public details?: any
  ) {
    super(message);
  }
}

// Usage:
throw new AppError('BOT_START_FAILED', 'Bot failed to start', 400, {
  reason: 'MT5 connection failed',
  userId: user.id
});
```

### 2. **Logging Standardization**
```typescript
// Structured logging
export interface LogEntry {
  timestamp: string;
  level: 'debug' | 'info' | 'warn' | 'error';
  function: string;
  userId?: string;
  message: string;
  data?: any;
  error?: any;
}

// Usage:
logger.info('bot_started', { userId, strategyId, botPid });
logger.error('bot_start_failed', { userId, error }, error);
```

### 3. **Request Validation**
```typescript
// Use Zod for all request validation
import { z } from 'zod';

const startBotSchema = z.object({
  strategyId: z.string().uuid(),
  config: z.object({
    riskPerTrade: z.number().min(0.1).max(5),
    maxPositions: z.number().int().min(1).max(10),
  })
});

// Validate:
const validated = startBotSchema.parse(await req.json());
```

### 4. **Response Standardization**
```typescript
// Standard response format
interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  meta?: {
    timestamp: string;
    requestId: string;
  };
}

// Usage:
return Response.json({
  success: true,
  data: insights,
  meta: {
    timestamp: new Date().toISOString(),
    requestId: crypto.randomUUID()
  }
});
```

## 📊 Monitoring & Observability

### Add Function Metrics
```sql
-- Create metrics table
CREATE TABLE edge_function_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  function_name TEXT NOT NULL,
  execution_time_ms INTEGER,
  success BOOLEAN,
  error_code TEXT,
  user_id UUID,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Track in each function:
await supabase.from('edge_function_metrics').insert({
  function_name: 'generate-ai-insights',
  execution_time_ms: Date.now() - startTime,
  success: true,
  user_id: user.id
});
```

### Add Alerting
```typescript
// Alert on function failures
if (errorRate > 10%) {
  await sendAdminAlert({
    severity: 'high',
    function: 'trigger-bot',
    message: 'High error rate detected',
    errorRate,
    affectedUsers
  });
}
```

## 🚀 New Functions to Create

### 1. **auto-trade-manager** (Advanced)
```typescript
// AI-powered auto-trading
// - Execute AI recommendations automatically
// - Risk management
// - Position sizing
// - Stop loss placement
```

### 2. **strategy-optimizer** (Advanced)
```typescript
// Automatic strategy parameter optimization
// - Backtest parameter variations
// - Find optimal settings
// - A/B test in paper trading
```

### 3. **market-data-fetcher** (Integration)
```typescript
// Fetch live market data
// - Price feeds
// - Economic calendar
// - News sentiment
// - Technical indicators
```

### 4. **reporting-generator** (Business)
```typescript
// Generate comprehensive reports
// - Daily/weekly/monthly summaries
// - PDF exports
// - Email delivery
// - Custom templates
```

### 5. **user-onboarding** (UX)
```typescript
// Guided onboarding flow
// - Step-by-step setup
// - Progress tracking
// - Help tooltips
// - Video tutorials
```

## 💰 Cost Optimization

### 1. **Reduce AI API Calls**
```typescript
// Cache similar queries
// Use cheaper models for simple tasks
// Batch requests when possible
// Implement smart rate limiting
```

### 2. **Optimize Database Queries**
```typescript
// Add indexes
// Use materialized views for analytics
// Implement query result caching
// Reduce real-time queries
```

### 3. **Implement Edge Caching**
```typescript
// Cache at CDN level
// Set proper cache headers
// Use stale-while-revalidate
```

## 📝 Documentation Needs

1. **API Documentation**
   - All function endpoints
   - Request/response formats
   - Error codes
   - Rate limits
   - Examples

2. **Architecture Diagrams**
   - Function call flows
   - Data flow diagrams
   - Integration points
   - Error handling paths

3. **Runbooks**
   - Incident response
   - Common issues & fixes
   - Deployment procedures
   - Rollback procedures

## ✅ Action Items

### Week 1
- [ ] Fix trigger-bot retry logic
- [ ] Add bot-health-monitor function
- [ ] Standardize error handling
- [ ] Add function metrics tracking

### Week 2
- [ ] Create trade-analyzer function
- [ ] Implement alert-manager
- [ ] Add rate limiting middleware
- [ ] Set up monitoring dashboard

### Week 3
- [ ] Build performance-calculator
- [ ] Create backup-manager
- [ ] Add request validation (Zod)
- [ ] Implement response standardization

### Week 4
- [ ] Create webhook system
- [ ] Build reporting-generator
- [ ] Add caching layer
- [ ] Documentation sprint

---

**Last Updated**: November 18, 2025
**Status**: Core AI functions fixed, ready for next phase
**Priority**: Focus on reliability and monitoring first, then advanced features

---

## ⚠️ Deploying edge functions: a git push is NOT a deploy

**Merging to `main` does not deploy an edge function.** Lovable syncs the
repository and marks the commit's edit `status: "completed"`, and
`read_file(ref="main")` will happily return the new source — but the version
*running* in Supabase is still the old one until an explicit function deploy
happens.

This was learned the expensive way. A cutoff was added to
`send-onboarding-nurture` specifically to stop it emailing long-abandoned
signups. The change was merged to `main`, Lovable reported the sync complete,
and the function was then invoked once to verify the fix. The old version was
still live, so that single invocation sent **74 real onboarding emails** to
people who had signed up between 3 weeks and 3 months earlier — precisely the
outcome the change existed to prevent. Deploying the function properly and
re-invoking returned `{"success":true,"emailsSent":0,"skippedTooOld":109,
"candidates":109}`, i.e. the fix works and had simply never been live.

### The rule

Never verify an edge-function change by invoking it until you have confirmed
the deploy landed. For any function with side effects — sending email,
charging a card, placing an order, writing to a third party — invoking it *is*
the side effect, and "I think it's deployed" is not good enough.

1. Merge/push the source.
2. **Explicitly deploy the function** (Lovable's agent: "deploy the edge
   function `<name>`"; or `supabase functions deploy <name>`).
3. Confirm the *running* version, ideally by an observable marker that costs
   nothing — a new field in the response shape, a version constant. Add one
   deliberately when the change is otherwise invisible from outside.
4. Only then re-enable whatever schedule or caller drives it.

### Sequencing rule for anything that sends

When a fix bounds a blast radius, the *bound* must be live before the thing
that triggers it. Order: deploy the bound → verify the bound → then repair the
caller (cron auth, schedule, feature flag). Repairing the caller first, or
"just testing once" first, means the unbounded version is what runs.

### Cron jobs authenticate with CRON_SECRET, not a JWT

`check-trial-expiry`, `send-onboarding-nurture` and `monitor-bot-health` all
require `Authorization: Bearer <CRON_SECRET>`. Two of the three cron jobs were
created with a Supabase JWT instead and had therefore been returning 401 on
every run since they shipped — silently, because `cron.job_run_details.status`
reads `succeeded` when the SQL merely *enqueues* the request. The HTTP result
lives in `net._http_response`; that is the only place a 401 shows up.

To re-point a job at the working secret without ever writing it into a query,
copy it from a job that already has it:

```sql
headers := jsonb_build_object(
  'Content-Type','application/json',
  'Authorization','Bearer ' || (
    SELECT substring(command from 'Bearer ([0-9a-f]{64})')
    FROM cron.job WHERE jobname = 'monitor-bot-health-job'))
```

Verify a job's health with the response body, never the run status:

```sql
SELECT id, status_code, content, error_msg, created
FROM net._http_response ORDER BY id DESC LIMIT 10;
```
