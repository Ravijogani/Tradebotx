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
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay, subMonths, addMonths, startOfWeek, endOfWeek } from "date-fns";
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

interface JournalEntry {
  id: string;
  trade_id: string;
  notes: string;
  tags: string[];
  screenshot_urls: string[];
  created_at: string;
  updated_at: string;
  trade: {
    symbol: string;
    trade_type: string;
    profit_loss: number;
    entry_price: number;
    exit_price: number;
    opened_at: string;
    closed_at: string;
    status: string;
    quantity: number;
  };
}

// ── Calendar Heatmap Component ──
function CalendarHeatmap({ entries, calendarMonth, setCalendarMonth }: {
  entries: JournalEntry[];
  calendarMonth: Date;
  setCalendarMonth: (d: Date) => void;
}) {
  const monthStart = startOfMonth(calendarMonth);
  const monthEnd = endOfMonth(calendarMonth);
  const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
  const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start: calStart, end: calEnd });
  const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  const dayPnl = useMemo(() => {
    const map = new Map<string, number>();
    entries.forEach(e => {
      if (!e.trade.closed_at) return;
      const key = format(new Date(e.trade.closed_at), 'yyyy-MM-dd');
      map.set(key, (map.get(key) || 0) + (e.trade.profit_loss || 0));
    });
    return map;
  }, [entries]);

  const dayCount = useMemo(() => {
    const map = new Map<string, number>();
    entries.forEach(e => {
      if (!e.trade.closed_at) return;
      const key = format(new Date(e.trade.closed_at), 'yyyy-MM-dd');
      map.set(key, (map.get(key) || 0) + 1);
    });
    return map;
  }, [entries]);

  const getCellColor = (day: Date) => {
    const key = format(day, 'yyyy-MM-dd');
    const pnl = dayPnl.get(key);
    if (pnl === undefined) return 'bg-muted/30';
    if (pnl > 0) return 'bg-green-500/70 dark:bg-green-500/60';
    if (pnl < 0) return 'bg-red-500/70 dark:bg-red-500/60';
    return 'bg-muted/50';
  };

  const isCurrentMonth = (day: Date) => day.getMonth() === calendarMonth.getMonth();

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <CalendarIcon className="w-4 h-4 text-primary" />
            Trading Calendar
          </CardTitle>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setCalendarMonth(subMonths(calendarMonth, 1))}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-sm font-medium min-w-[120px] text-center">{format(calendarMonth, 'MMMM yyyy')}</span>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setCalendarMonth(addMonths(calendarMonth, 1))}>
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-7 gap-1">
          {weekdays.map(d => (
            <div key={d} className="text-[10px] text-muted-foreground text-center font-medium py-1">{d}</div>
          ))}
          <TooltipProvider>
            {days.map((day, i) => {
              const key = format(day, 'yyyy-MM-dd');
              const pnl = dayPnl.get(key);
              const count = dayCount.get(key);
              return (
                <Tooltip key={i}>
                  <TooltipTrigger asChild>
                    <div className={`aspect-square rounded-md flex items-center justify-center text-[11px] font-medium transition-colors cursor-default
                      ${getCellColor(day)} 
                      ${!isCurrentMonth(day) ? 'opacity-25' : ''}
                      ${isSameDay(day, new Date()) ? 'ring-2 ring-primary ring-offset-1 ring-offset-background' : ''}
                    `}>
                      {day.getDate()}
                    </div>
                  </TooltipTrigger>
                  {pnl !== undefined && (
                    <TooltipContent>
                      <p className="font-semibold">{format(day, 'MMM dd, yyyy')}</p>
                      <p className={pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                        P&L: {pnl >= 0 ? '+' : ''}₹{pnl.toFixed(2)}
                      </p>
                      <p className="text-xs text-muted-foreground">{count} trade(s)</p>
                    </TooltipContent>
                  )}
                </Tooltip>
              );
            })}
          </TooltipProvider>
        </div>
        <div className="flex items-center gap-4 mt-3 justify-center text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-green-500/70 inline-block" /> Profit</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-red-500/70 inline-block" /> Loss</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-muted/30 inline-block" /> No trades</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Stat Card Component ──
function StatCard({ icon: Icon, label, value, subValue, color }: {
  icon: any; label: string; value: string; subValue?: string; color: string;
}) {
  return (
    <Card className="relative overflow-hidden">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{label}</p>
            <p className="text-2xl font-bold mt-1">{value}</p>
            {subValue && <p className="text-xs text-muted-foreground mt-0.5">{subValue}</p>}
          </div>
          <div className={`p-2 rounded-lg ${color}`}>
            <Icon className="w-4 h-4" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main Component ──
export default function TradeJournal() {
  const [user, setUser] = useState<any>(null);
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
    const updateEffectiveTheme = () => {
      if (theme === "light") setEffectiveTheme("light");
      else if (theme === "dark") setEffectiveTheme("dark");
      else {
        setEffectiveTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      }
    };
    updateEffectiveTheme();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => { if (theme === "system") updateEffectiveTheme(); };
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
      setEntries(data as any);
      setFilteredEntries(data as any);
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
    const totalPnl = entries.reduce((sum, e) => sum + (e.trade.profit_loss || 0), 0);
    const winningTrades = entries.filter(e => e.trade.profit_loss > 0);
    const losingTrades = entries.filter(e => e.trade.profit_loss < 0);
    const winRate = entries.length > 0 ? (winningTrades.length / entries.length) * 100 : 0;
    const avgWin = winningTrades.length > 0 ? winningTrades.reduce((s, e) => s + e.trade.profit_loss, 0) / winningTrades.length : 0;
    const avgLoss = losingTrades.length > 0 ? losingTrades.reduce((s, e) => s + e.trade.profit_loss, 0) / losingTrades.length : 0;
    const profitFactor = Math.abs(avgLoss) > 0 ? avgWin / Math.abs(avgLoss) : 0;
    const bestTrade = entries.length > 0 ? Math.max(...entries.map(e => e.trade.profit_loss || 0)) : 0;
    const worstTrade = entries.length > 0 ? Math.min(...entries.map(e => e.trade.profit_loss || 0)) : 0;

    // Symbol breakdown
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
      .map(([symbol, data]) => ({ symbol, ...data, winRate: (data.wins / data.count) * 100 }))
      .sort((a, b) => b.pnl - a.pnl);

    // Daily P&L for bar chart
    const dailyMap = new Map<string, number>();
    entries.forEach(e => {
      if (!e.trade.closed_at) return;
      const key = format(new Date(e.trade.closed_at), 'MMM dd');
      dailyMap.set(key, (dailyMap.get(key) || 0) + (e.trade.profit_loss || 0));
    });
    const dailyPnl = Array.from(dailyMap.entries())
      .map(([date, pnl]) => ({ date, pnl: Number(pnl.toFixed(2)) }))
      .slice(-14); // last 14 days

    const mostUsedTags = allTags.map(tag => ({
      tag, count: entries.filter(e => e.tags?.includes(tag)).length
    })).sort((a, b) => b.count - a.count).slice(0, 5);

    return {
      totalEntries: entries.length,
      totalPnl,
      winningTrades: winningTrades.length,
      losingTrades: losingTrades.length,
      winRate,
      avgWin,
      avgLoss,
      profitFactor,
      bestTrade,
      worstTrade,
      symbolBreakdown,
      dailyPnl,
      mostUsedTags,
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
    doc.text(`Generated: ${format(new Date(), 'PPP')} | Entries: ${filteredEntries.length} | Total P&L: ₹${analytics.totalPnl.toFixed(2)}`, 14, 30);

    const tableData = filteredEntries.map(entry => [
      format(new Date(entry.created_at), 'MM/dd/yyyy'),
      entry.trade.symbol,
      entry.trade.trade_type,
      `₹${entry.trade.profit_loss?.toFixed(2) || '0.00'}`,
      entry.tags?.join(', ') || '-',
      entry.notes?.substring(0, 50) + (entry.notes?.length > 50 ? '...' : '')
    ]);

    autoTable(doc, {
      head: [['Date', 'Symbol', 'Type', 'P/L', 'Tags', 'Notes']],
      body: tableData,
      startY: 38,
      styles: { fontSize: 8 }
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
        <AppSidebar activeTab="journal" onTabChange={() => {}} />

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
              {/* Page header */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                <div>
                  <div className="flex items-center gap-3">
                    <Button variant="ghost" size="icon" onClick={() => navigate('/dashboard')} className="h-8 w-8">
                      <ArrowLeft className="w-4 h-4" />
                    </Button>
                    <div>
                      <h1 className="text-2xl font-bold flex items-center gap-2">
                        <BookOpen className="w-6 h-6 text-primary" />
                        Trade Journal
                      </h1>
                      <p className="text-sm text-muted-foreground">Track, analyze & master your trading patterns</p>
                    </div>
                  </div>
                </div>
                <Button onClick={exportToPDF} size="sm" className="gap-2">
                  <Download className="w-4 h-4" />
                  Export PDF
                </Button>
              </div>

              {/* Stats Row */}
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
                <StatCard icon={FileText} label="Journal Entries" value={String(analytics.totalEntries)} color="bg-primary/10 text-primary" />
                <StatCard
                  icon={DollarSign}
                  label="Total P&L"
                  value={`${analytics.totalPnl >= 0 ? '+' : ''}₹${analytics.totalPnl.toFixed(0)}`}
                  color={analytics.totalPnl >= 0 ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"}
                />
                <StatCard icon={Target} label="Win Rate" value={`${analytics.winRate.toFixed(1)}%`} subValue={`${analytics.winningTrades}W / ${analytics.losingTrades}L`} color="bg-blue-500/10 text-blue-500" />
                <StatCard icon={Activity} label="Profit Factor" value={analytics.profitFactor.toFixed(2)} color="bg-purple-500/10 text-purple-500" />
                <StatCard icon={Flame} label="Streak" value={`${analytics.journalStreak}d`} subValue="consecutive days" color="bg-orange-500/10 text-orange-500" />
              </div>

              <Tabs defaultValue="entries" className="space-y-5">
                <TabsList className="bg-background border">
                  <TabsTrigger value="entries" className="gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
                    <FileText className="w-4 h-4" />
                    Entries
                  </TabsTrigger>
                  <TabsTrigger value="calendar" className="gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
                    <CalendarIcon className="w-4 h-4" />
                    Calendar
                  </TabsTrigger>
                  <TabsTrigger value="analytics" className="gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
                    <BarChart3 className="w-4 h-4" />
                    Analytics
                  </TabsTrigger>
                </TabsList>

                {/* ── ENTRIES TAB ── */}
                <TabsContent value="entries" className="space-y-4">
                  {/* Filters */}
                  <Card className="p-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                      <div className="relative">
                        <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
                        <Input placeholder="Search notes or symbols..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-9 h-9" />
                      </div>
                      <Select value={selectedTag} onValueChange={setSelectedTag}>
                        <SelectTrigger className="h-9">
                          <Tag className="w-3.5 h-3.5 mr-1.5" />
                          <SelectValue placeholder="Filter by tag" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Tags</SelectItem>
                          {allTags.map(tag => <SelectItem key={tag} value={tag}>{tag}</SelectItem>)}
                        </SelectContent>
                      </Select>
                      <Select value={outcomeFilter} onValueChange={setOutcomeFilter}>
                        <SelectTrigger className="h-9">
                          <Filter className="w-3.5 h-3.5 mr-1.5" />
                          <SelectValue placeholder="Outcome" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Trades</SelectItem>
                          <SelectItem value="winning">Winning</SelectItem>
                          <SelectItem value="losing">Losing</SelectItem>
                        </SelectContent>
                      </Select>
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button variant="outline" className="h-9 justify-start text-sm">
                            <CalendarIcon className="w-3.5 h-3.5 mr-1.5" />
                            {dateRange.from ? (dateRange.to ? <>{format(dateRange.from, "MMM dd")} – {format(dateRange.to, "MMM dd")}</> : format(dateRange.from, "MMM dd, yyyy")) : "Date range"}
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                          <Calendar mode="range" selected={{ from: dateRange.from, to: dateRange.to }} onSelect={(range) => setDateRange({ from: range?.from, to: range?.to })} numberOfMonths={2} />
                        </PopoverContent>
                      </Popover>
                    </div>
                  </Card>

                  {/* Trade entries */}
                  <div className="space-y-3">
                    {filteredEntries.length === 0 ? (
                      <Card className="p-12 text-center">
                        <BookOpen className="w-10 h-10 mx-auto text-muted-foreground/50 mb-3" />
                        <h3 className="text-lg font-semibold mb-1">No journal entries</h3>
                        <p className="text-sm text-muted-foreground">
                          {entries.length === 0 ? "Start adding notes to your trades from the dashboard" : "Try adjusting your filters"}
                        </p>
                      </Card>
                    ) : (
                      filteredEntries.map(entry => {
                        const pnl = entry.trade.profit_loss || 0;
                        const isWin = pnl > 0;
                        const pctChange = entry.trade.entry_price ? ((entry.trade.exit_price - entry.trade.entry_price) / entry.trade.entry_price * 100 * (entry.trade.trade_type.toLowerCase() === 'sell' ? -1 : 1)) : 0;

                        return (
                          <Card key={entry.id} className="group hover:shadow-md transition-all duration-200 overflow-hidden">
                            <div className={`h-1 ${isWin ? 'bg-green-500' : 'bg-red-500'}`} />
                            <div className="p-4 sm:p-5">
                              {/* Top row */}
                              <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-3">
                                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isWin ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                                    {isWin ? <ArrowUpRight className="w-5 h-5 text-green-500" /> : <ArrowDownRight className="w-5 h-5 text-red-500" />}
                                  </div>
                                  <div>
                                    <div className="flex items-center gap-2">
                                      <h3 className="text-lg font-bold">{entry.trade.symbol}</h3>
                                      <Badge variant="outline" className="text-[10px] h-5">{entry.trade.trade_type}</Badge>
                                    </div>
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                                      <Clock className="w-3 h-3" />
                                      {format(new Date(entry.created_at), 'dd MMM yyyy, hh:mm a')}
                                    </div>
                                  </div>
                                </div>

                                <div className="flex items-center gap-3">
                                  <div className="text-right">
                                    <div className={`text-lg font-bold ${isWin ? 'text-green-500' : 'text-red-500'}`}>
                                      {isWin ? '+' : ''}₹{pnl.toFixed(2)}
                                    </div>
                                    <div className={`text-xs ${isWin ? 'text-green-500/70' : 'text-red-500/70'}`}>
                                      {pctChange >= 0 ? '+' : ''}{pctChange.toFixed(2)}%
                                    </div>
                                  </div>
                                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <Button variant="ghost" size="icon" className="h-7 w-7">
                                      <Edit2 className="w-3.5 h-3.5" />
                                    </Button>
                                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteEntry(entry.id)}>
                                      <Trash2 className="w-3.5 h-3.5 text-destructive" />
                                    </Button>
                                  </div>
                                </div>
                              </div>

                              {/* Notes */}
                              {entry.notes && (
                                <p className="text-sm text-muted-foreground mb-3 whitespace-pre-wrap leading-relaxed bg-muted/30 rounded-lg p-3">
                                  {entry.notes}
                                </p>
                              )}

                              {/* Tags */}
                              {entry.tags && entry.tags.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mb-3">
                                  {entry.tags.map(tag => (
                                    <Badge key={tag} variant="outline" className="text-[10px] h-5 gap-1">
                                      <Tag className="w-2.5 h-2.5" />
                                      {tag}
                                    </Badge>
                                  ))}
                                </div>
                              )}

                              {/* Trade details */}
                              <div className="grid grid-cols-4 gap-3 pt-3 border-t border-border/50">
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Entry</p>
                                  <p className="text-sm font-semibold">{entry.trade.entry_price?.toFixed(2)}</p>
                                </div>
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Exit</p>
                                  <p className="text-sm font-semibold">{entry.trade.exit_price?.toFixed(2)}</p>
                                </div>
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Qty</p>
                                  <p className="text-sm font-semibold">{entry.trade.quantity || '-'}</p>
                                </div>
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Duration</p>
                                  <p className="text-sm font-semibold">
                                    {entry.trade.closed_at && entry.trade.opened_at
                                      ? formatDuration(new Date(entry.trade.opened_at), new Date(entry.trade.closed_at))
                                      : '-'}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </Card>
                        );
                      })
                    )}
                  </div>
                </TabsContent>

                {/* ── CALENDAR TAB ── */}
                <TabsContent value="calendar">
                  <CalendarHeatmap entries={entries} calendarMonth={calendarMonth} setCalendarMonth={setCalendarMonth} />
                </TabsContent>

                {/* ── ANALYTICS TAB ── */}
                <TabsContent value="analytics" className="space-y-4">
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {/* Win/Loss Pie */}
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Win/Loss Ratio</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="h-48">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie data={winPieData} cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={4} dataKey="value">
                                {winPieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                              </Pie>
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="flex justify-center gap-6 text-sm">
                          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-green-500" />{analytics.winningTrades} Wins</span>
                          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-500" />{analytics.losingTrades} Losses</span>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Key Metrics */}
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Key Metrics</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {[
                          { label: 'Avg Win', value: `+₹${analytics.avgWin.toFixed(2)}`, color: 'text-green-500' },
                          { label: 'Avg Loss', value: `₹${analytics.avgLoss.toFixed(2)}`, color: 'text-red-500' },
                          { label: 'Best Trade', value: `+₹${analytics.bestTrade.toFixed(2)}`, color: 'text-green-500' },
                          { label: 'Worst Trade', value: `₹${analytics.worstTrade.toFixed(2)}`, color: 'text-red-500' },
                          { label: 'Profit Factor', value: analytics.profitFactor.toFixed(2), color: 'text-foreground' },
                        ].map(m => (
                          <div key={m.label} className="flex justify-between items-center py-1.5 border-b border-border/30 last:border-0">
                            <span className="text-sm text-muted-foreground">{m.label}</span>
                            <span className={`text-sm font-bold ${m.color}`}>{m.value}</span>
                          </div>
                        ))}
                      </CardContent>
                    </Card>

                    {/* Top Tags */}
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                          <Tag className="w-4 h-4 text-primary" />
                          Top Tags
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2.5">
                        {analytics.mostUsedTags.length === 0 ? (
                          <p className="text-sm text-muted-foreground text-center py-6">No tags yet</p>
                        ) : (
                          analytics.mostUsedTags.map((item, i) => (
                            <div key={item.tag} className="flex items-center gap-3">
                              <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-xs font-bold text-primary">{i + 1}</div>
                              <span className="flex-1 text-sm font-medium">{item.tag}</span>
                              <Badge variant="secondary" className="text-[10px]">{item.count}</Badge>
                            </div>
                          ))
                        )}
                      </CardContent>
                    </Card>
                  </div>

                  {/* Daily P&L Chart */}
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">Daily P&L (Last 14 Trading Days)</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={analytics.dailyPnl}>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                            <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                            <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                            <RechartsTooltip
                              contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}
                              formatter={(value: number) => [`₹${value.toFixed(2)}`, 'P&L']}
                            />
                            <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                              {analytics.dailyPnl.map((entry, i) => (
                                <Cell key={i} fill={entry.pnl >= 0 ? 'hsl(var(--success))' : 'hsl(var(--destructive))'} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Symbol Breakdown */}
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">Symbol Breakdown</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b">
                              <th className="text-left py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Symbol</th>
                              <th className="text-right py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Trades</th>
                              <th className="text-right py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Win Rate</th>
                              <th className="text-right py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">P&L</th>
                            </tr>
                          </thead>
                          <tbody>
                            {analytics.symbolBreakdown.map(s => (
                              <tr key={s.symbol} className="border-b border-border/30 last:border-0">
                                <td className="py-2 px-3 font-semibold">{s.symbol}</td>
                                <td className="py-2 px-3 text-right text-muted-foreground">{s.count}</td>
                                <td className="py-2 px-3 text-right">{s.winRate.toFixed(0)}%</td>
                                <td className={`py-2 px-3 text-right font-semibold ${s.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                  {s.pnl >= 0 ? '+' : ''}₹{s.pnl.toFixed(2)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>
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
