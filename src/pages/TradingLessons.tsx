import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { format, formatDistanceToNow } from "date-fns";
import {
  Search,
  Brain,
  ArrowLeft,
  ArrowUpRight,
  ArrowDownRight,
  DollarSign,
  Sparkles,
  Clock,
  Activity,
  Filter,
  GraduationCap,
  Info,
} from "lucide-react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/dashboard/AppSidebar";
import { ThemeToggle } from "@/components/dashboard/ThemeToggle";
import { UserProfileDropdown } from "@/components/dashboard/UserProfileDropdown";
import logo from "@/assets/tradebotx-logo.png";
import logoWhite from "@/assets/tradebotx-logo-white.png";
import { useTheme } from "@/components/theme-provider";
import type { LucideIcon } from "lucide-react";
import type { User } from "@supabase/supabase-js";
import type { Tables } from "@/integrations/supabase/types";

type Lesson = Tables<"trade_lessons">;

interface LessonContext {
  adx?: number;
  session?: string;
  hour?: number;
  context_timing?: string;
  source?: string;
}

const getContext = (lesson: Lesson): LessonContext => {
  const ctx = lesson.context;
  if (ctx && typeof ctx === "object" && !Array.isArray(ctx)) return ctx as LessonContext;
  return {};
};

const isAiSource = (lesson: Lesson) => getContext(lesson).source === "ai";

// ── Stat Card (same pattern as Trade Journal) ──
function StatCard({ icon: Icon, label, value, subValue, badgeText, iconBg }: {
  icon: LucideIcon; label: string; value: string; subValue?: string; badgeText?: string; iconBg: string;
}) {
  return (
    <Card className="relative overflow-hidden">
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${iconBg}`}>
            <Icon className="w-5 h-5" />
          </div>
          {badgeText && (
            <Badge variant="outline" className="text-[10px] h-5 font-semibold">{badgeText}</Badge>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider mb-1">{label}</p>
        <p className="text-2xl font-bold leading-tight">{value}</p>
        {subValue && <p className="text-xs text-muted-foreground mt-1">{subValue}</p>}
      </CardContent>
    </Card>
  );
}

export default function TradingLessons() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [symbolFilter, setSymbolFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [effectiveTheme, setEffectiveTheme] = useState<"light" | "dark">("dark");
  const navigate = useNavigate();
  const { toast } = useToast();
  const { theme } = useTheme();

  useEffect(() => {
    const update = () => {
      if (theme === "light") setEffectiveTheme("light");
      else if (theme === "dark") setEffectiveTheme("dark");
      else setEffectiveTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    };
    update();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => { if (theme === "system") update(); };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  const currentLogo = effectiveTheme === "light" ? logo : logoWhite;

  useEffect(() => { checkUser(); }, []);

  const checkUser = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { navigate("/auth/login"); return; }
    setUser(session.user);
    loadLessons(session.user.id);
  };

  const loadLessons = async (userId: string) => {
    setLoading(true);
    const { data, error } = await supabase
      .from("trade_lessons")
      .select("*")
      .eq("user_id", userId)
      .order("created_at", { ascending: false });

    if (error) {
      toast({ title: "Error", description: "Failed to load trading lessons", variant: "destructive" });
    } else {
      setLessons(data || []);
    }
    setLoading(false);
  };

  // Live updates — trade_lessons is in the realtime publication for this page.
  useEffect(() => {
    if (!user) return;
    const channel = supabase
      .channel("trade-lessons-changes")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "trade_lessons", filter: `user_id=eq.${user.id}` },
        (payload) => {
          const incoming = payload.new as Lesson;
          setLessons((prev) => (prev.some((l) => l.id === incoming.id) ? prev : [incoming, ...prev]));
        }
      )
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [user]);

  const symbols = useMemo(
    () => Array.from(new Set(lessons.map((l) => l.symbol).filter(Boolean))).sort(),
    [lessons]
  );

  const filteredLessons = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return lessons.filter((l) => {
      if (q && !(l.lesson?.toLowerCase().includes(q) || l.symbol?.toLowerCase().includes(q))) return false;
      if (symbolFilter !== "all" && l.symbol !== symbolFilter) return false;
      if (sourceFilter === "ai" && !isAiSource(l)) return false;
      if (sourceFilter === "deterministic" && isAiSource(l)) return false;
      return true;
    });
  }, [lessons, searchQuery, symbolFilter, sourceFilter]);

  const stats = useMemo(() => {
    const totalLoss = lessons.reduce((sum, l) => sum + Math.abs(Number(l.loss_amount) || 0), 0);
    const aiCount = lessons.filter(isAiSource).length;
    return {
      total: lessons.length,
      totalLoss,
      aiCount,
      fallbackCount: lessons.length - aiCount,
      latest: lessons[0]?.created_at || null,
    };
  }, [lessons]);

  if (loading || !user) {
    return (
      <div className="flex items-center justify-center h-screen gap-3">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-muted-foreground">Loading lessons...</span>
      </div>
    );
  }

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        <AppSidebar activeTab="lessons" onTabChange={(tab) => navigate(`/dashboard?tab=${tab}`)} />
        <div className="flex-1 flex flex-col">
          <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-14 items-center gap-4 px-4 sm:px-6">
              <SidebarTrigger className="-ml-1" />
              <img src={currentLogo} alt="TradeBotX" className="h-7 w-auto" />
              <div className="flex-1" />
              <ThemeToggle />
              <UserProfileDropdown user={user} onSettingsClick={() => navigate("/dashboard")} />
            </div>
          </header>

          <main className="flex-1 overflow-y-auto bg-muted/20">
            <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-5">
              {/* Page title */}
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" onClick={() => navigate("/dashboard")} className="h-8 w-8">
                  <ArrowLeft className="w-4 h-4" />
                </Button>
                <div>
                  <h1 className="text-2xl font-bold">Trading Lessons</h1>
                  <p className="text-xs text-muted-foreground">
                    Every losing trade, reviewed honestly by the bot — so the same mistake doesn't repeat.
                  </p>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <StatCard
                  icon={GraduationCap}
                  label="Lessons Learned"
                  value={`${stats.total}`}
                  subValue="from losing trades"
                  badgeText="TOTAL"
                  iconBg="bg-primary/10 text-primary"
                />
                <StatCard
                  icon={DollarSign}
                  label="Cost of Learning"
                  value={`-$${stats.totalLoss.toFixed(2)}`}
                  subValue="across analyzed trades"
                  iconBg="bg-red-500/10 text-red-500"
                />
                <StatCard
                  icon={Sparkles}
                  label="AI vs Pattern"
                  value={`${stats.aiCount} / ${stats.fallbackCount}`}
                  subValue="AI analysis / pattern-based"
                  iconBg="bg-blue-500/10 text-blue-500"
                />
                <StatCard
                  icon={Clock}
                  label="Latest Lesson"
                  value={stats.latest ? format(new Date(stats.latest), "MMM dd") : "—"}
                  subValue={stats.latest ? formatDistanceToNow(new Date(stats.latest), { addSuffix: true }) : "no lessons yet"}
                  iconBg="bg-orange-500/10 text-orange-500"
                />
              </div>

              {/* Filters */}
              <Card className="p-3">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
                    <Input
                      placeholder="Search lessons or symbol..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-8 h-9 text-sm"
                    />
                  </div>
                  <Select value={symbolFilter} onValueChange={setSymbolFilter}>
                    <SelectTrigger className="h-9 text-sm">
                      <Activity className="w-3 h-3 mr-1" />
                      <SelectValue placeholder="Symbol" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Symbols</SelectItem>
                      {symbols.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Select value={sourceFilter} onValueChange={setSourceFilter}>
                    <SelectTrigger className="h-9 text-sm">
                      <Filter className="w-3 h-3 mr-1" />
                      <SelectValue placeholder="Source" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Sources</SelectItem>
                      <SelectItem value="ai">AI Analysis</SelectItem>
                      <SelectItem value="deterministic">Pattern-Based</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </Card>

              {/* Lessons */}
              {filteredLessons.length === 0 ? (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                      <Brain className="w-7 h-7" />
                    </div>
                    <p className="font-semibold">
                      {lessons.length === 0 ? "No lessons yet" : "No lessons match your filters"}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1 max-w-sm">
                      {lessons.length === 0
                        ? "The bot logs one every time a trade closes at a loss — its own honest post-mortem on what went wrong."
                        : "Try clearing the search or changing the symbol and source filters."}
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {filteredLessons.map((lesson) => {
                    const ctx = getContext(lesson);
                    const ai = ctx.source === "ai";
                    const isBuy = (lesson.direction || "").toUpperCase().includes("BUY");
                    const estimatedAtExit = (ctx.context_timing || "").includes("AT EXIT");
                    const loss = Math.abs(Number(lesson.loss_amount) || 0);

                    return (
                      <Card key={lesson.id} className="transition-all hover:border-primary/40 hover:shadow-sm">
                        <CardContent className="p-5 space-y-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-bold text-sm">{lesson.symbol}</span>
                            <Badge variant="outline" className="text-[10px] h-5 gap-1 font-semibold">
                              {isBuy ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                              {(lesson.direction || "").toUpperCase()}
                            </Badge>
                            <Badge variant="secondary" className="text-[10px] h-5 gap-1 font-semibold">
                              {ai ? <Sparkles className="w-3 h-3" /> : <Activity className="w-3 h-3" />}
                              {ai ? "AI Analysis" : "Pattern-Based"}
                            </Badge>
                            <div className="flex-1" />
                            <span className="text-sm font-bold text-red-500">-${loss.toFixed(2)}</span>
                          </div>

                          <p className="text-sm leading-relaxed">{lesson.lesson}</p>

                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                            {ctx.session && <span>Session: {ctx.session}</span>}
                            {typeof ctx.adx === "number" && <span>ADX: {ctx.adx.toFixed(1)}</span>}
                            {typeof ctx.hour === "number" && <span>Hour: {String(ctx.hour).padStart(2, "0")}:00</span>}
                            {lesson.ticket && <span>Ticket #{lesson.ticket}</span>}
                            <span>{formatDistanceToNow(new Date(lesson.created_at), { addSuffix: true })}</span>
                          </div>

                          {estimatedAtExit && (
                            <p className="flex items-start gap-1.5 text-[11px] text-muted-foreground italic">
                              <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
                              Market conditions estimated at exit, not entry.
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
