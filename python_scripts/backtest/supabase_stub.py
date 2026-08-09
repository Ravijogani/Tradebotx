"""
Fake `supabase` module, installed into sys.modules before the live bot
file is imported for backtesting -- same reasoning as mt5_stub.py.

hybrid_trading_bot_multiuser.py does `from supabase import create_client,
Client` and constructs a real client at module scope
(`supabase: Client = create_client(args.supabase_url, SUPABASE_KEY_RESOLVED)`).
A backtest has no business writing trade records, audit logs, or anything
else to the production database -- this stub makes that structurally
impossible rather than relying on the dummy URL/key we pass in silently
failing to connect. `SupabaseTradeDB` (the class that wraps `supabase.*`
calls for logging trades) is never invoked by the backtest engine, so
nothing here needs to do anything beyond "exist and not crash."
"""


class _FakeQueryBuilder:
    """Swallows the fluent .table().select().eq()... chains used
    throughout the bot file's Supabase calls, always returning itself so
    chaining never breaks, and a harmless empty-ish result on execute()."""

    def __getattr__(self, name):
        def _chain(*args, **kwargs):
            return self
        return _chain

    def execute(self):
        return _FakeResult()


class _FakeResult:
    data = []
    count = 0


class _FakeAuth:
    def get_user(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, *args, **kwargs):
        self.auth = _FakeAuth()

    def table(self, *args, **kwargs):
        return _FakeQueryBuilder()

    def from_(self, *args, **kwargs):
        return _FakeQueryBuilder()

    def rpc(self, *args, **kwargs):
        return _FakeQueryBuilder()


def create_client(url: str, key: str) -> Client:
    return Client()
