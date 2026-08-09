import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useToast } from "@/hooks/use-toast";
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay, subMonths, addMonths, startOfWeek, endOfWeek, getISOWeek } from "date-fns";
import {
  Search,
  Calendar as CalendarIcon,
  Filter,
  Download,
  TrendingUp,
  TrendingDown,
  BookOpen,
  Tag,
  BarChart3,
  FileText,
  Edit2,
  Trash2,
  ArrowLeft,
  Flame,
  Target,
  DollarSign,
  Activity,
  ChevronLeft,
  ChevronRight,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  CheckCircle2,
  Timer,
} from "lucide-react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/dashboard/AppSidebar";
import { ThemeToggle } from "@/components/dashboard/ThemeToggle";
import { UserProfileDropdown } from "@/components/dashboard/UserProfileDropdown";
import logo from "@/assets/tradebotx-logo.png";
import logoWhite from "@/assets/tradebotx-logo-white.png";
import { useTheme } from "@/components/theme-provider";
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip } from "recharts";
import type { LucideIcon } from "lucide-react";
import type { User } from "@supabase/supabase-js";
import type { Tables } from "@/integrations/supabase/types";

interface JournalEntry {
  id: string;
  trade_id: string;
  notes: string | null;
  tags: string[] | null;
  screenshot_urls: string[] | null;
  created_at: string;
  updated_at: string;
  // trade_notes.trade_id is NOT NULL + ON DELETE CASCADE, so the embedded
  // trade always exists for any note row that survives.
  trade: Pick<Tables<"trades">, "symbol" | "trade_type" | "profit_loss" | "entry_price" | "exit_price" | "opened_at" | "closed_at" | "status" | "quantity">;
}

// ── Monthly P&L Calendar (TradeFXBook-inspired) ──
function MonthlyPnLCalendar({ entries, calendarMonth, setCalendarMonth }: {
  entries: JournalEntry[];
  calendarMonth: Date;
  setCalendarMonth: (d: Date) => void;
}) {
  const monthStart = startOfMonth(calendarMonth);
  const monthEnd = endOfMonth(calendarMonth);
  const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
  const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start: calStart, end: calEnd });
  const weekdays = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

  const dayPnl = useMemo(() => {
    const map = new Map<string, { pnl: number; count: number }>();
    entries.forEach(e => {
      if (!e.trade.closed_at) return;
      const key = format(new Date(e.trade.closed_at), 'yyyy-MM-dd');
      const existing = map.get(key) || { pnl: 0, count: 0 };
      existing.pnl += e.trade.profit_loss || 0;
      existing.count++;
      map.set(key, existing);
    });
    return map;
  }, [entries]);

  // Group days into weeks for weekly summary
  const weeks: Date[][] = [];
  for (let i = 0; i < days.length; i += 7) {
    weeks.push(days.slice(i, i + 7));
  }

  const getWeeklyPnl = (week: Date[]) => {
    let total = 0;
    let hasTrades = false;
    week.forEach(day => {
      const key = format(day, 'yyyy-MM-dd');
      const data = dayPnl.get(key);
      if (data) { total += data.pnl; hasTrades = true; }
    });
    return { total, hasTrades };
  };

  const monthlyTotal = useMemo(() => {
    let total = 0;
    dayPnl.forEach((data, key) => {
      const date = new Date(key);
      if (date >= monthStart && date <= monthEnd) total += data.pnl;
    });
    return total;
  }, [dayPnl, monthStart, monthEnd]);

  const isCurrentMonth = (day: Date) => day.getMonth() === calendarMonth.getMonth();

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setCalendarMonth(subMonths(calendarMonth, 1))}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-sm font-bold min-w-[120px] text-center">{format(calendarMonth, 'MMMM yyyy')}</span>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setCalendarMonth(addMonths(calendarMonth, 1))}>
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
          <div className={`text-sm font-bold ${monthlyTotal >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            Monthly: {monthlyTotal >= 0 ? '+' : ''}${monthlyTotal.toFixed(2)}
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-3 pb-3">
        {/* Weekday headers + Weekly column */}
        <div className="grid grid-cols-8 gap-px mb-1">
          {weekdays.map((d, i) => (
            <div key={i} className="text-[10px] text-muted-foreground text-center font-semibold py-1">{d}</div>
          ))}
          <div className="text-[10px] text-muted-foreground text-center font-semibold py-1">Weekly</div>
        </div>

        {/* Calendar grid */}
        {weeks.map((week, wi) => {
          const weekSummary = getWeeklyPnl(week);
          return (
            <div key={wi} className="grid grid-cols-8 gap-px mb-px">
              {week.map((day, di) => {
                const key = format(day, 'yyyy-MM-dd');
                const data = dayPnl.get(key);
                const hasTrades = !!data;
                const pnl = data?.pnl || 0;
                const inMonth = isCurrentMonth(day);
                const isToday = isSameDay(day, new Date());

                return (
                  <TooltipProvider key={di}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className={`
                          relative aspect-square flex flex-col items-center justify-center rounded-md text-[11px] transition-all cursor-default
                          ${!inMonth ? 'opacity-20' : ''}
                          ${isToday ? 'ring-2 ring-primary ring-offset-1 ring-offset-background' : ''}
                          ${hasTrades && pnl > 0 ? 'bg-green-500/15 dark:bg-green-500/20' : ''}
                          ${hasTrades && pnl < 0 ? 'bg-red-500/15 dark:bg-red-500/20' : ''}
                          ${hasTrades && pnl === 0 ? 'bg-muted/40' : ''}
                          ${!hasTrades ? 'bg-muted/10 hover:bg-muted/20' : ''}
                        `}>
                          <span className="font-medium">{day.getDate()}</span>
                          {hasTrades && (
                            <span className={`text-[8px] font-bold leading-tight ${pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                              {pnl >= 0 ? '+' : ''}${Math.abs(pnl) >= 1000 ? `${(pnl / 1000).toFixed(1)}k` : pnl.toFixed(0)}
                            </span>
                          )}
                        </div>
                      </TooltipTrigger>
                      {hasTrades && (
                        <TooltipContent>
                          <p className="font-semibold">{format(day, 'EEE, MMM dd')}</p>
                          <p className={pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                            P&L: {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                          </p>
                          <p className="text-xs text-muted-foreground">{data?.count} trade(s)</p>
                        </TooltipContent>
                      )}
                    </Tooltip>
                  </TooltipProvider>
                );
              })}
              {/* Weekly summary */}
              <div className={`flex flex-col items-center justify-center rounded-md text-[10px] ${weekSummary.hasTrades ? 'bg-muted/30' : ''}`}>
                {weekSummary.hasTrades ? (
                  <>
                    <span className="text-[8px] text-muted-foreground uppercase font-semibold">Weekly</span>
                    <span className={`font-bold ${weekSummary.total >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${weekSummary.total.toFixed(0)}
                    </span>
                  </>
                ) : (
                  <span className="text-[8px] text-muted-foreground">—</span>
                )}
              </div>
            </div>
          );
        })}

        {/* Legend */}
        <div className="flex items-center gap-4 mt-3 justify-center text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-green-500/30 inline-block" /> Profit Day</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-red-500/30 inline-block" /> Loss Day</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded ring-2 ring-primary inline-block" /> Today</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ── TradeFXBook-style Stat Card ──
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

// ── Main Component ──
export default function TradeJournal() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [filteredEntries, setFilteredEntries] = useState<JournalEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState<string>("all");
  const [dateRange, setDateRange] = useState<{ from: Date | undefined; to: Date | undefined }>({ from: undefined, to: undefined });
  const [outcomeFilter, setOutcomeFilter] = useState<string>("all");
  const [calendarMonth, setCalendarMonth] = useState(new Date());
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
    loadJournalEntries(session.user.id);
  };

  const loadJournalEntries = async (userId: string) => {
    setLoading(true);
    const { data, error } = await supabase
      .from("trade_notes")
      .select(`*, trade:trades(symbol, trade_type, profit_loss, entry_price, exit_price, opened_at, closed_at, status, quantity)`)
      .eq("user_id", userId)
      .order("created_at", { ascending: false });

    if (error) {
      toast({ title: "Error", description: "Failed to load journal entries", variant: "destructive" });
    } else {
      const journalEntries = (data || []) as JournalEntry[];
      setEntries(journalEntries);
      setFilteredEntries(journalEntries);
    }
    setLoading(false);
  };

  const allTags = Array.from(new Set(entries.flatMap(e => e.tags || [])));

  useEffect(() => {
    let filtered = [...entries];
    if (searchQuery) {
      filtered = filtered.filter(entry =>
        entry.notes?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entry.trade.symbol?.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    if (selectedTag !== "all") filtered = filtered.filter(entry => entry.tags?.includes(selectedTag));
    if (dateRange.from) filtered = filtered.filter(entry => dateRange.from && new Date(entry.created_at) >= dateRange.from);
    if (dateRange.to) filtered = filtered.filter(entry => dateRange.to && new Date(entry.created_at) <= dateRange.to);
    if (outcomeFilter === "winning") filtered = filtered.filter(entry => entry.trade.profit_loss > 0);
    else if (outcomeFilter === "losing") filtered = filtered.filter(entry => entry.trade.profit_loss < 0);
    setFilteredEntries(filtered);
  }, [searchQuery, selectedTag, dateRange, outcomeFilter, entries]);

  // Analytics
  const analytics = useMemo(() => {
    const closedEntries = entries.filter(e => e.trade.status === 'closed');
    const openEntries = entries.filter(e => e.trade.status !== 'closed');
    const realizedPnl = closedEntries.reduce((sum, e) => sum + (e.trade.profit_loss || 0), 0);
    const unrealizedPnl = openEntries.reduce((sum, e) => sum + (e.trade.profit_loss || 0), 0);
    const totalPnl = realizedPnl + unrealizedPnl;
    const winningTrades = closedEntries.filter(e => e.trade.profit_loss > 0);
    const losingTrades = closedEntries.filter(e => e.trade.profit_loss < 0);
    const winRate = closedEntries.length > 0 ? (winningTrades.length / closedEntries.length) * 100 : 0;
    const avgWin = winningTrades.length > 0 ? winningTrades.reduce((s, e) => s + e.trade.profit_loss, 0) / winningTrades.length : 0;
    const avgLoss = losingTrades.length > 0 ? losingTrades.reduce((s, e) => s + e.trade.profit_loss, 0) / losingTrades.length : 0;
    const profitFactor = Math.abs(avgLoss) > 0 ? avgWin / Math.abs(avgLoss) : 0;
    const bestTrade = closedEntries.length > 0 ? Math.max(...closedEntries.map(e => e.trade.profit_loss || 0)) : 0;
    const worstTrade = closedEntries.length > 0 ? Math.min(...closedEntries.map(e => e.trade.profit_loss || 0)) : 0;

    const symbolMap = new Map<string, { count: number; pnl: number; wins: number }>();
    entries.forEach(e => {
      const sym = e.trade.symbol;
      const existing = symbolMap.get(sym) || { count: 0, pnl: 0, wins: 0 };
      existing.count++;
      existing.pnl += e.trade.profit_loss || 0;
      if (e.trade.profit_loss > 0) existing.wins++;
      symbolMap.set(sym, existing);
    });
    const symbolBreakdown = Array.from(symbolMap.entries())
      .map(([symbol, data]) => ({ symbol, ...data, winRate: data.count > 0 ? (data.wins / data.count) * 100 : 0 }))
      .sort((a, b) => b.pnl - a.pnl);

    const dailyMap = new Map<string, number>();
    entries.forEach(e => {
      if (!e.trade.closed_at) return;
      const key = format(new Date(e.trade.closed_at), 'MMM dd');
      dailyMap.set(key, (dailyMap.get(key) || 0) + (e.trade.profit_loss || 0));
    });
    const dailyPnl = Array.from(dailyMap.entries())
      .map(([date, pnl]) => ({ date, pnl: Number(pnl.toFixed(2)) }))
      .slice(-14);

    const mostUsedTags = allTags.map(tag => ({
      tag, count: entries.filter(e => e.tags?.includes(tag)).length
    })).sort((a, b) => b.count - a.count).slice(0, 5);

    return {
      totalEntries: entries.length,
      totalPnl, realizedPnl, unrealizedPnl,
      closedTrades: closedEntries.length,
      openTrades: openEntries.length,
      winningTrades: winningTrades.length,
      losingTrades: losingTrades.length,
      winRate, avgWin, avgLoss, profitFactor, bestTrade, worstTrade,
      symbolBreakdown, dailyPnl, mostUsedTags,
      journalStreak: calculateStreak(entries),
    };
  }, [entries, allTags]);

  function calculateStreak(entries: JournalEntry[]) {
    if (entries.length === 0) return 0;
    const dates = entries.map(e => format(new Date(e.created_at), 'yyyy-MM-dd'));
    const uniqueDates = Array.from(new Set(dates)).sort().reverse();
    let streak = 0;
    const today = format(new Date(), 'yyyy-MM-dd');
    if (uniqueDates[0] === today || uniqueDates[0] === format(new Date(Date.now() - 86400000), 'yyyy-MM-dd')) {
      streak = 1;
      for (let i = 1; i < uniqueDates.length; i++) {
        const prev = new Date(uniqueDates[i - 1]);
        const curr = new Date(uniqueDates[i]);
        if (Math.floor((prev.getTime() - curr.getTime()) / 86400000) === 1) streak++;
        else break;
      }
    }
    return streak;
  }

  const exportToPDF = () => {
    const doc = new jsPDF();
    doc.setFontSize(20);
    doc.text("Trade Journal Report — TradeBotX", 14, 20);
    doc.setFontSize(11);
    doc.text(`Generated: ${format(new Date(), 'PPP')} | Entries: ${filteredEntries.length} | Total P&L: $${analytics.totalPnl.toFixed(2)}`, 14, 30);
    const tableData = filteredEntries.map(entry => [
      format(new Date(entry.created_at), 'MM/dd/yyyy'),
      entry.trade.symbol,
      entry.trade.trade_type,
      `$${entry.trade.profit_loss?.toFixed(2) || '0.00'}`,
      entry.tags?.join(', ') || '-',
      (entry.notes || '').substring(0, 50) + ((entry.notes?.length || 0) > 50 ? '...' : '')
    ]);
    autoTable(doc, {
      head: [['Date', 'Symbol', 'Type', 'P/L', 'Tags', 'Notes']],
      body: tableData, startY: 38, styles: { fontSize: 8 }
    });
    doc.save(`TradeBotX-Journal-${format(new Date(), 'yyyy-MM-dd')}.pdf`);
    toast({ title: "Exported", description: "Journal exported to PDF" });
  };

  const deleteEntry = async (entryId: string) => {
    const { error } = await supabase.from("trade_notes").delete().eq("id", entryId);
    if (error) {
      toast({ title: "Error", description: "Failed to delete", variant: "destructive" });
    } else {
      setEntries(entries.filter(e => e.id !== entryId));
      toast({ title: "Deleted", description: "Journal entry removed" });
    }
  };

  if (loading || !user) {
    return (
      <div className="flex items-center justify-center h-screen gap-3">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-muted-foreground">Loading journal...</span>
      </div>
    );
  }

  const winPieData = [
    { name: 'Wins', value: analytics.winningTrades, color: 'hsl(var(--success))' },
    { name: 'Losses', value: analytics.losingTrades, color: 'hsl(var(--destructive))' },
  ];

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        <AppSidebar activeTab="journal" onTabChange={(tab) => navigate(`/dashboard?tab=${tab}`)} />
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-14 items-center gap-4 px-4 sm:px-6">
              <SidebarTrigger className="-ml-1" />
              <img src={currentLogo} alt="TradeBotX" className="h-7 w-auto" />
              <div className="flex-1" />
              <ThemeToggle />
              <UserProfileDropdown user={user} onSettingsClick={() => navigate('/dashboard')} />
            </div>
          </header>

          <main className="flex-1 overflow-y-auto bg-muted/20">
            <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-5">
              {/* Page title */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} className="h-8 w-8">
                    <ArrowLeft className="w-4 h-4" />
                  </Button>
                  <div>
                    <h1 className="text-2xl font-bold">Journal</h1>
                    <p className="text-xs text-muted-foreground">{format(new Date(), 'EEE, MMM dd')}</p>
                  </div>
                </div>
                <Button onClick={exportToPDF} size="sm" variant="outline" className="gap-2">
                  <Download className="w-4 h-4" />
                  Export PDF
                </Button>
              </div>

              {/* ── TradeFXBook-style Stats Row ── */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <StatCard
                  icon={DollarSign}
                  label="Total P&L"
                  value={`${analytics.totalPnl >= 0 ? '+' : ''}$${analytics.totalPnl.toFixed(2)}`}
                  subValue={`→ ${entries.length} trades`}
                  badgeText="TOTAL"
                  iconBg="bg-primary/10 text-primary"
                />
                <StatCard
                  icon={Timer}
                  label="Unrealized"
                  value={`${analytics.unrealizedPnl >= 0 ? '+' : ''}$${analytics.unrealizedPnl.toFixed(2)}`}
                  subValue={`${analytics.openTrades} open positions`}
                  iconBg="bg-orange-500/10 text-orange-500"
                />
                <StatCard
                  icon={CheckCircle2}
                  label="Realized"
                  value={`${analytics.realizedPnl >= 0 ? '+' : ''}$${analytics.realizedPnl.toFixed(2)}`}
                  subValue={`${analytics.closedTrades} closed trades`}
                  iconBg="bg-green-500/10 text-green-500"
                />
                <StatCard
                  icon={Target}
                  label="Win Rate"
                  value={`${analytics.winRate.toFixed(0)}%`}
                  subValue={`${analytics.winningTrades}W / ${analytics.losingTrades}L`}
                  iconBg="bg-blue-500/10 text-blue-500"
                />
              </div>

              {/* ── Main Content: 2 column layout ── */}
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
                {/* Left: Tabs (3 cols) */}
                <div className="lg:col-span-3">
                  <Tabs defaultValue="entries" className="space-y-4">
                    <TabsList className="bg-background border w-full justify-start">
                      <TabsTrigger value="entries" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
                        <FileText className="w-3.5 h-3.5" />
                        Entries
                      </TabsTrigger>
                      <TabsTrigger value="analytics" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
                        <BarChart3 className="w-3.5 h-3.5" />
                        Analytics
                      </TabsTrigger>
                    </TabsList>

                    {/* ── ENTRIES TAB ── */}
                    <TabsContent value="entries" className="space-y-3">
                      <Card className="p-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                          <div className="relative">
                            <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
                            <Input placeholder="Search..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-8 h-9 text-sm" />
                          </div>
                          <Select value={selectedTag} onValueChange={setSelectedTag}>
                            <SelectTrigger className="h-9 text-sm">
                              <Tag className="w-3 h-3 mr-1" />
                              <SelectValue placeholder="Tag" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">All Tags</SelectItem>
                              {allTags.map(tag => <SelectItem key={tag} value={tag}>{tag}</SelectItem>)}
                            </SelectContent>
                          </Select>
                          <Select value={outcomeFilter} onValueChange={setOutcomeFilter}>
                            <SelectTrigger className="h-9 text-sm">
                              <Filter className="w-3 h-3 mr-1" />
                              <SelectValue placeholder="Outcome" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">All</SelectItem>
                              <SelectItem value="winning">Winners</SelectItem>
                              <SelectItem value="losing">Losers</SelectItem>
                            </SelectContent>
                          </Select>
                          <Popover>
                            <PopoverTrigger asChild>
                              <Button variant="outline" className="h-9 justify-start text-xs">
                                <CalendarIcon className="w-3 h-3 mr-1" />
                                {dateRange.from ? (dateRange.to ? <>{format(dateRange.from, "MMM dd")} – {format(dateRange.to, "MMM dd")}</> : format(dateRange.from, "MMM dd")) : "Date range"}
                              </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-0" align="start">
                              <Calendar mode="range" selected={{ from: dateRange.from, to: dateRange.to }} onSelect={(range) => setDateRange({ from: range?.from, to: range?.to })} numberOfMonths={2} />
                            </PopoverContent>
                          </Popover>
                        </div>
                      </Card>

                      <div className="space-y-2">
                        {filteredEntries.length === 0 ? (
                          <Card className="p-10 text-center">
                            <BookOpen className="w-8 h-8 mx-auto text-muted-foreground/40 mb-2" />
                            <h3 className="font-semibold mb-1">No entries</h3>
                            <p className="text-xs text-muted-foreground">{entries.length === 0 ? "Add notes to trades from dashboard" : "Adjust filters"}</p>
                          </Card>
                        ) : (
                          filteredEntries.map(entry => {
                            const pnl = entry.trade.profit_loss || 0;
                            const isWin = pnl > 0;
                            const pctChange = entry.trade.entry_price ? ((entry.trade.exit_price - entry.trade.entry_price) / entry.trade.entry_price * 100 * (entry.trade.trade_type.toLowerCase() === 'sell' ? -1 : 1)) : 0;

                            return (
                              <Card key={entry.id} className="group hover:shadow-md transition-all overflow-hidden">
                                <div className={`h-0.5 ${isWin ? 'bg-green-500' : 'bg-red-500'}`} />
                                <div className="p-4">
                                  <div className="flex items-start justify-between mb-2">
                                    <div className="flex items-center gap-2.5">
                                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${isWin ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                                        {isWin ? <ArrowUpRight className="w-4 h-4 text-green-500" /> : <ArrowDownRight className="w-4 h-4 text-red-500" />}
                                      </div>
                                      <div>
                                        <div className="flex items-center gap-1.5">
                                          <span className="font-bold">{entry.trade.symbol}</span>
                                          <Badge variant="outline" className="text-[9px] h-4 px-1">{entry.trade.trade_type}</Badge>
                                        </div>
                                        <p className="text-[10px] text-muted-foreground flex items-center gap-1 mt-0.5">
                                          <Clock className="w-2.5 h-2.5" />
                                          {format(new Date(entry.created_at), 'dd MMM yy, hh:mm a')}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <div className="text-right">
                                        <div className={`font-bold ${isWin ? 'text-green-500' : 'text-red-500'}`}>
                                          {isWin ? '+' : ''}${pnl.toFixed(2)}
                                        </div>
                                        <div className={`text-[10px] ${isWin ? 'text-green-500/70' : 'text-red-500/70'}`}>
                                          {pctChange >= 0 ? '+' : ''}{pctChange.toFixed(2)}%
                                        </div>
                                      </div>
                                      <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <Button variant="ghost" size="icon" className="h-6 w-6"><Edit2 className="w-3 h-3" /></Button>
                                        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => deleteEntry(entry.id)}><Trash2 className="w-3 h-3 text-destructive" /></Button>
                                      </div>
                                    </div>
                                  </div>

                                  {entry.notes && (
                                    <p className="text-xs text-muted-foreground mb-2 whitespace-pre-wrap bg-muted/30 rounded-md p-2.5 leading-relaxed">{entry.notes}</p>
                                  )}

                                  {entry.tags?.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mb-2">
                                      {entry.tags.map(tag => (
                                        <Badge key={tag} variant="outline" className="text-[9px] h-4 px-1.5 gap-0.5">
                                          <Tag className="w-2 h-2" />{tag}
                                        </Badge>
                                      ))}
                                    </div>
                                  )}

                                  <div className="grid grid-cols-4 gap-2 pt-2 border-t border-border/40 text-[10px]">
                                    <div><span className="text-muted-foreground">Entry</span><p className="font-semibold text-xs">{entry.trade.entry_price?.toFixed(2)}</p></div>
                                    <div><span className="text-muted-foreground">Exit</span><p className="font-semibold text-xs">{entry.trade.exit_price?.toFixed(2)}</p></div>
                                    <div><span className="text-muted-foreground">Qty</span><p className="font-semibold text-xs">{entry.trade.quantity || '-'}</p></div>
                                    <div><span className="text-muted-foreground">Duration</span><p className="font-semibold text-xs">{entry.trade.closed_at && entry.trade.opened_at ? formatDuration(new Date(entry.trade.opened_at), new Date(entry.trade.closed_at)) : '-'}</p></div>
                                  </div>
                                </div>
                              </Card>
                            );
                          })
                        )}
                      </div>
                    </TabsContent>

                    {/* ── ANALYTICS TAB ── */}
                    <TabsContent value="analytics" className="space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Win/Loss Pie */}
                        <Card>
                          <CardHeader className="pb-1"><CardTitle className="text-sm">Win/Loss Ratio</CardTitle></CardHeader>
                          <CardContent>
                            <div className="h-44">
                              <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                  <Pie data={winPieData} cx="50%" cy="50%" innerRadius={45} outerRadius={65} paddingAngle={4} dataKey="value">
                                    {winPieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                                  </Pie>
                                </PieChart>
                              </ResponsiveContainer>
                            </div>
                            <div className="flex justify-center gap-5 text-xs">
                              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" />{analytics.winningTrades} Wins</span>
                              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" />{analytics.losingTrades} Losses</span>
                            </div>
                          </CardContent>
                        </Card>

                        {/* Key Metrics */}
                        <Card>
                          <CardHeader className="pb-1"><CardTitle className="text-sm">Key Metrics</CardTitle></CardHeader>
                          <CardContent className="space-y-2">
                            {[
                              { label: 'Avg Win', value: `+$${analytics.avgWin.toFixed(2)}`, color: 'text-green-500' },
                              { label: 'Avg Loss', value: `$${analytics.avgLoss.toFixed(2)}`, color: 'text-red-500' },
                              { label: 'Best Trade', value: `+$${analytics.bestTrade.toFixed(2)}`, color: 'text-green-500' },
                              { label: 'Worst Trade', value: `$${analytics.worstTrade.toFixed(2)}`, color: 'text-red-500' },
                              { label: 'Profit Factor', value: analytics.profitFactor.toFixed(2), color: 'text-foreground' },
                              { label: 'Journal Streak', value: `${analytics.journalStreak} days`, color: 'text-foreground' },
                            ].map(m => (
                              <div key={m.label} className="flex justify-between items-center py-1 border-b border-border/20 last:border-0">
                                <span className="text-xs text-muted-foreground">{m.label}</span>
                                <span className={`text-xs font-bold ${m.color}`}>{m.value}</span>
                              </div>
                            ))}
                          </CardContent>
                        </Card>
                      </div>

                      {/* Daily P&L Chart */}
                      <Card>
                        <CardHeader className="pb-1"><CardTitle className="text-sm">Daily P&L (Last 14 Days)</CardTitle></CardHeader>
                        <CardContent>
                          <div className="h-52">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={analytics.dailyPnl}>
                                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                                <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                                <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                                <RechartsTooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }} formatter={(value: number) => [`$${value.toFixed(2)}`, 'P&L']} />
                                <Bar dataKey="pnl" radius={[3, 3, 0, 0]}>
                                  {analytics.dailyPnl.map((entry, i) => <Cell key={i} fill={entry.pnl >= 0 ? 'hsl(var(--success))' : 'hsl(var(--destructive))'} />)}
                                </Bar>
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </CardContent>
                      </Card>

                      {/* Symbol Breakdown + Tags */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <Card>
                          <CardHeader className="pb-1"><CardTitle className="text-sm">Symbol Breakdown</CardTitle></CardHeader>
                          <CardContent>
                            <table className="w-full text-xs">
                              <thead><tr className="border-b">
                                <th className="text-left py-1.5 text-muted-foreground font-medium">Symbol</th>
                                <th className="text-right py-1.5 text-muted-foreground font-medium">Trades</th>
                                <th className="text-right py-1.5 text-muted-foreground font-medium">Win%</th>
                                <th className="text-right py-1.5 text-muted-foreground font-medium">P&L</th>
                              </tr></thead>
                              <tbody>
                                {analytics.symbolBreakdown.slice(0, 8).map(s => (
                                  <tr key={s.symbol} className="border-b border-border/20">
                                    <td className="py-1.5 font-semibold">{s.symbol}</td>
                                    <td className="py-1.5 text-right text-muted-foreground">{s.count}</td>
                                    <td className="py-1.5 text-right">{s.winRate.toFixed(0)}%</td>
                                    <td className={`py-1.5 text-right font-semibold ${s.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>{s.pnl >= 0 ? '+' : ''}${s.pnl.toFixed(2)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </CardContent>
                        </Card>
                        <Card>
                          <CardHeader className="pb-1"><CardTitle className="text-sm flex items-center gap-1.5"><Tag className="w-3.5 h-3.5 text-primary" />Top Tags</CardTitle></CardHeader>
                          <CardContent className="space-y-2">
                            {analytics.mostUsedTags.length === 0 ? (
                              <p className="text-xs text-muted-foreground text-center py-6">No tags yet</p>
                            ) : analytics.mostUsedTags.map((item, i) => (
                              <div key={item.tag} className="flex items-center gap-2">
                                <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center text-[10px] font-bold text-primary">{i + 1}</div>
                                <span className="flex-1 text-xs font-medium">{item.tag}</span>
                                <Badge variant="secondary" className="text-[9px] h-4">{item.count}</Badge>
                              </div>
                            ))}
                          </CardContent>
                        </Card>
                      </div>
                    </TabsContent>
                  </Tabs>
                </div>

                {/* Right: Monthly P&L Calendar (2 cols) */}
                <div className="lg:col-span-2">
                  <MonthlyPnLCalendar entries={entries} calendarMonth={calendarMonth} setCalendarMonth={setCalendarMonth} />
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}

function formatDuration(start: Date, end: Date): string {
  const ms = end.getTime() - start.getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ${mins % 60}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}
