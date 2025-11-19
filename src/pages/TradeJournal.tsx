import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { format } from "date-fns";
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
  Trash2
} from "lucide-react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

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
  };
}

export default function TradeJournal() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [filteredEntries, setFilteredEntries] = useState<JournalEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState<string>("all");
  const [dateRange, setDateRange] = useState<{ from: Date | undefined; to: Date | undefined }>({ from: undefined, to: undefined });
  const [outcomeFilter, setOutcomeFilter] = useState<string>("all");
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    checkUser();
  }, []);

  const checkUser = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) {
      navigate("/auth/login");
      return;
    }
    setUser(session.user);
    loadJournalEntries(session.user.id);
  };

  const loadJournalEntries = async (userId: string) => {
    setLoading(true);
    const { data, error } = await supabase
      .from("trade_notes")
      .select(`
        *,
        trade:trades(
          symbol,
          trade_type,
          profit_loss,
          entry_price,
          exit_price,
          opened_at,
          closed_at,
          status
        )
      `)
      .eq("user_id", userId)
      .order("created_at", { ascending: false });

    if (error) {
      console.error("Error loading journal entries:", error);
      toast({
        title: "Error",
        description: "Failed to load journal entries",
        variant: "destructive",
      });
    } else {
      setEntries(data as any);
      setFilteredEntries(data as any);
    }
    setLoading(false);
  };

  // Extract all unique tags
  const allTags = Array.from(new Set(entries.flatMap(e => e.tags || [])));

  // Filter entries based on search, tags, date range, and outcome
  useEffect(() => {
    let filtered = [...entries];

    // Search filter
    if (searchQuery) {
      filtered = filtered.filter(entry =>
        entry.notes?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entry.trade.symbol?.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Tag filter
    if (selectedTag !== "all") {
      filtered = filtered.filter(entry => entry.tags?.includes(selectedTag));
    }

    // Date range filter
    if (dateRange.from) {
      filtered = filtered.filter(entry => {
        const entryDate = new Date(entry.created_at);
        return dateRange.from && entryDate >= dateRange.from;
      });
    }
    if (dateRange.to) {
      filtered = filtered.filter(entry => {
        const entryDate = new Date(entry.created_at);
        return dateRange.to && entryDate <= dateRange.to;
      });
    }

    // Outcome filter
    if (outcomeFilter === "winning") {
      filtered = filtered.filter(entry => entry.trade.profit_loss > 0);
    } else if (outcomeFilter === "losing") {
      filtered = filtered.filter(entry => entry.trade.profit_loss < 0);
    }

    setFilteredEntries(filtered);
  }, [searchQuery, selectedTag, dateRange, outcomeFilter, entries]);

  // Analytics calculations
  const analytics = {
    totalEntries: entries.length,
    winningTrades: entries.filter(e => e.trade.profit_loss > 0).length,
    losingTrades: entries.filter(e => e.trade.profit_loss < 0).length,
    mostUsedTags: allTags.map(tag => ({
      tag,
      count: entries.filter(e => e.tags?.includes(tag)).length
    })).sort((a, b) => b.count - a.count).slice(0, 5),
    avgNotesLength: entries.reduce((acc, e) => acc + (e.notes?.length || 0), 0) / (entries.length || 1),
    journalStreak: calculateStreak(entries)
  };

  function calculateStreak(entries: JournalEntry[]) {
    if (entries.length === 0) return 0;
    
    const dates = entries.map(e => format(new Date(e.created_at), 'yyyy-MM-dd'));
    const uniqueDates = Array.from(new Set(dates)).sort().reverse();
    
    let streak = 0;
    const today = format(new Date(), 'yyyy-MM-dd');
    
    if (uniqueDates[0] === today || uniqueDates[0] === format(new Date(Date.now() - 86400000), 'yyyy-MM-dd')) {
      streak = 1;
      for (let i = 1; i < uniqueDates.length; i++) {
        const prevDate = new Date(uniqueDates[i-1]);
        const currDate = new Date(uniqueDates[i]);
        const diffDays = Math.floor((prevDate.getTime() - currDate.getTime()) / 86400000);
        if (diffDays === 1) {
          streak++;
        } else {
          break;
        }
      }
    }
    return streak;
  }

  const exportToPDF = () => {
    const doc = new jsPDF();
    
    doc.setFontSize(20);
    doc.text("Trade Journal Report", 14, 20);
    doc.setFontSize(12);
    doc.text(`Generated: ${format(new Date(), 'PPP')}`, 14, 30);
    doc.text(`Total Entries: ${filteredEntries.length}`, 14, 38);

    const tableData = filteredEntries.map(entry => [
      format(new Date(entry.created_at), 'MM/dd/yyyy'),
      entry.trade.symbol,
      entry.trade.trade_type,
      `$${entry.trade.profit_loss?.toFixed(2) || '0.00'}`,
      entry.tags?.join(', ') || '-',
      entry.notes?.substring(0, 50) + (entry.notes?.length > 50 ? '...' : '')
    ]);

    autoTable(doc, {
      head: [['Date', 'Symbol', 'Type', 'P/L', 'Tags', 'Notes']],
      body: tableData,
      startY: 45,
      styles: { fontSize: 8 }
    });

    doc.save(`trade-journal-${format(new Date(), 'yyyy-MM-dd')}.pdf`);
    
    toast({
      title: "Success",
      description: "Journal exported to PDF successfully",
    });
  };

  const deleteEntry = async (entryId: string) => {
    const { error } = await supabase
      .from("trade_notes")
      .delete()
      .eq("id", entryId);

    if (error) {
      toast({
        title: "Error",
        description: "Failed to delete journal entry",
        variant: "destructive",
      });
    } else {
      setEntries(entries.filter(e => e.id !== entryId));
      toast({
        title: "Success",
        description: "Journal entry deleted",
      });
    }
  };

  if (loading || !user) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return (
    <DashboardLayout user={user}>
      <div className="container mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <BookOpen className="w-8 h-8 text-primary" />
              Trade Journal
            </h1>
            <p className="text-muted-foreground mt-1">
              Review and analyze your trading notes and patterns
            </p>
          </div>
          <Button onClick={exportToPDF} className="gap-2">
            <Download className="w-4 h-4" />
            Export PDF
          </Button>
        </div>

        <Tabs defaultValue="entries" className="space-y-6">
          <TabsList>
            <TabsTrigger value="entries" className="gap-2">
              <FileText className="w-4 h-4" />
              Entries
            </TabsTrigger>
            <TabsTrigger value="analytics" className="gap-2">
              <BarChart3 className="w-4 h-4" />
              Analytics
            </TabsTrigger>
          </TabsList>

          <TabsContent value="entries" className="space-y-6">
            {/* Filters */}
            <Card className="p-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="relative">
                  <Search className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search notes or symbols..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>

                <Select value={selectedTag} onValueChange={setSelectedTag}>
                  <SelectTrigger>
                    <Tag className="w-4 h-4 mr-2" />
                    <SelectValue placeholder="Filter by tag" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Tags</SelectItem>
                    {allTags.map(tag => (
                      <SelectItem key={tag} value={tag}>{tag}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={outcomeFilter} onValueChange={setOutcomeFilter}>
                  <SelectTrigger>
                    <Filter className="w-4 h-4 mr-2" />
                    <SelectValue placeholder="Filter by outcome" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Trades</SelectItem>
                    <SelectItem value="winning">Winning Trades</SelectItem>
                    <SelectItem value="losing">Losing Trades</SelectItem>
                  </SelectContent>
                </Select>

                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="justify-start">
                      <CalendarIcon className="w-4 h-4 mr-2" />
                      {dateRange.from ? (
                        dateRange.to ? (
                          <>
                            {format(dateRange.from, "MMM dd")} - {format(dateRange.to, "MMM dd")}
                          </>
                        ) : (
                          format(dateRange.from, "MMM dd, yyyy")
                        )
                      ) : (
                        "Date range"
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="range"
                      selected={{ from: dateRange.from, to: dateRange.to }}
                      onSelect={(range) => setDateRange({ from: range?.from, to: range?.to })}
                      numberOfMonths={2}
                    />
                  </PopoverContent>
                </Popover>
              </div>
            </Card>

            {/* Journal Entries List */}
            <div className="space-y-4">
              {filteredEntries.length === 0 ? (
                <Card className="p-12 text-center">
                  <BookOpen className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-xl font-semibold mb-2">No journal entries found</h3>
                  <p className="text-muted-foreground">
                    {entries.length === 0 
                      ? "Start adding notes to your trades to build your journal"
                      : "Try adjusting your filters"}
                  </p>
                </Card>
              ) : (
                filteredEntries.map(entry => (
                  <Card key={entry.id} className="p-6 hover:shadow-lg transition-shadow">
                    <div className="flex justify-between items-start mb-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-xl font-bold">{entry.trade.symbol}</h3>
                          <Badge variant={entry.trade.trade_type === "BUY" ? "default" : "secondary"}>
                            {entry.trade.trade_type}
                          </Badge>
                          <Badge variant={entry.trade.profit_loss >= 0 ? "default" : "destructive"} className="gap-1">
                            {entry.trade.profit_loss >= 0 ? (
                              <TrendingUp className="w-3 h-3" />
                            ) : (
                              <TrendingDown className="w-3 h-3" />
                            )}
                            ${Math.abs(entry.trade.profit_loss || 0).toFixed(2)}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {format(new Date(entry.created_at), 'PPP p')}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="sm">
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          onClick={() => deleteEntry(entry.id)}
                        >
                          <Trash2 className="w-4 h-4 text-destructive" />
                        </Button>
                      </div>
                    </div>

                    {entry.notes && (
                      <p className="text-sm mb-4 whitespace-pre-wrap">{entry.notes}</p>
                    )}

                    {entry.tags && entry.tags.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-4">
                        {entry.tags.map(tag => (
                          <Badge key={tag} variant="outline" className="gap-1">
                            <Tag className="w-3 h-3" />
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    )}

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t">
                      <div>
                        <p className="text-xs text-muted-foreground">Entry</p>
                        <p className="font-semibold">${entry.trade.entry_price?.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Exit</p>
                        <p className="font-semibold">${entry.trade.exit_price?.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Opened</p>
                        <p className="text-sm">{format(new Date(entry.trade.opened_at), 'MM/dd/yy')}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Closed</p>
                        <p className="text-sm">
                          {entry.trade.closed_at ? format(new Date(entry.trade.closed_at), 'MM/dd/yy') : '-'}
                        </p>
                      </div>
                    </div>
                  </Card>
                ))
              )}
            </div>
          </TabsContent>

          <TabsContent value="analytics" className="space-y-6">
            {/* Analytics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="p-6">
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Total Entries</h3>
                <p className="text-3xl font-bold">{analytics.totalEntries}</p>
              </Card>
              <Card className="p-6">
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Winning Trades</h3>
                <p className="text-3xl font-bold text-green-500">{analytics.winningTrades}</p>
              </Card>
              <Card className="p-6">
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Losing Trades</h3>
                <p className="text-3xl font-bold text-red-500">{analytics.losingTrades}</p>
              </Card>
              <Card className="p-6">
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Journal Streak</h3>
                <p className="text-3xl font-bold">{analytics.journalStreak} days</p>
              </Card>
            </div>

            {/* Most Used Tags */}
            <Card className="p-6">
              <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Tag className="w-5 h-5 text-primary" />
                Most Used Tags
              </h3>
              <div className="space-y-3">
                {analytics.mostUsedTags.map((item, index) => (
                  <div key={item.tag} className="flex items-center gap-4">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-bold text-primary">
                      {index + 1}
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold">{item.tag}</p>
                      <p className="text-sm text-muted-foreground">{item.count} entries</p>
                    </div>
                    <div className="w-24 bg-muted rounded-full h-2">
                      <div 
                        className="bg-primary h-2 rounded-full" 
                        style={{ width: `${(item.count / analytics.totalEntries) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Journal Insights */}
            <Card className="p-6">
              <h3 className="text-xl font-bold mb-4">Journal Insights</h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Average Note Length</span>
                  <span className="font-semibold">{Math.round(analytics.avgNotesLength)} characters</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Win Rate</span>
                  <span className="font-semibold">
                    {analytics.totalEntries > 0 
                      ? `${((analytics.winningTrades / analytics.totalEntries) * 100).toFixed(1)}%`
                      : '0%'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Entries This Week</span>
                  <span className="font-semibold">
                    {entries.filter(e => {
                      const weekAgo = new Date();
                      weekAgo.setDate(weekAgo.getDate() - 7);
                      return new Date(e.created_at) > weekAgo;
                    }).length}
                  </span>
                </div>
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
