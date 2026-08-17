import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { supabase } from "@/integrations/supabase/client";
import { 
  ArrowUpRight, 
  ArrowDownRight, 
  Download, 
  FileText,
  Filter,
  Calendar as CalendarIcon,
  Search,
  X
} from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import { cn } from "@/lib/utils";
import { TradeJournalDialog } from "./TradeJournalDialog";
import { ShareableTradeCard } from "./ShareableTradeCard";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import type { Tables } from "@/integrations/supabase/types";

import { TradeReasoning, TradeOutcomeReasoning, type TradeWhy, type TradeOutcome } from "./TradeReasoning";

type Trade = Tables<"trades">;

export const TradesListEnhanced = () => {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [filteredTrades, setFilteredTrades] = useState<Trade[]>([]);
  const [dateRange, setDateRange] = useState<{ from?: Date; to?: Date }>({});
  const [symbolFilter, setSymbolFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    loadTrades();
    
    // Set up realtime subscription for trades
    const channel = supabase
      .channel('trades-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'trades'
        },
        async (payload) => {
          console.log('Trade change:', payload);
          // Get current user to verify this trade belongs to them
          const { data: { user } } = await supabase.auth.getUser();
          if (user && payload.new && (payload.new as Partial<Trade>).user_id === user.id) {
            loadTrades();
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  useEffect(() => {
    applyFilters();
  }, [trades, dateRange, symbolFilter, statusFilter]);

  const loadTrades = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id)
      .order("opened_at", { ascending: false });

    setTrades(data || []);
  };

  const applyFilters = () => {
    let filtered = [...trades];

    // Date range filter
    if (dateRange.from) {
      filtered = filtered.filter(
        (trade) => new Date(trade.opened_at) >= dateRange.from!
      );
    }
    if (dateRange.to) {
      filtered = filtered.filter(
        (trade) => new Date(trade.opened_at) <= dateRange.to!
      );
    }

    // Symbol filter
    if (symbolFilter) {
      filtered = filtered.filter((trade) =>
        trade.symbol.toLowerCase().includes(symbolFilter.toLowerCase())
      );
    }

    // Status filter
    if (statusFilter && statusFilter !== "all") {
      filtered = filtered.filter((trade) => trade.status === statusFilter);
    }

    setFilteredTrades(filtered);
  };

  const clearFilters = () => {
    setDateRange({});
    setSymbolFilter("");
    setStatusFilter("all");
  };

  const exportToCSV = () => {
    const headers = ["Symbol", "Type", "Entry Price", "Exit Price", "P&L", "Status", "Opened At"];
    const rows = filteredTrades.map((trade) => [
      trade.symbol,
      trade.trade_type,
      trade.entry_price.toFixed(2),
      trade.exit_price ? trade.exit_price.toFixed(2) : "N/A",
      trade.profit_loss ? trade.profit_loss.toFixed(2) : "0.00",
      trade.status,
      new Date(trade.opened_at).toLocaleString(),
    ]);

    const csvContent = [
      headers.join(","),
      ...rows.map((row) => row.join(",")),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `trades-export-${format(new Date(), "yyyy-MM-dd")}.csv`;
    a.click();
  };

  const exportToPDF = () => {
    const doc = new jsPDF();
    
    // Add title
    doc.setFontSize(18);
    doc.text("Trade History Report", 14, 20);
    doc.setFontSize(11);
    doc.text(`Generated: ${format(new Date(), "PPP")}`, 14, 28);

    // Add table
    autoTable(doc, {
      startY: 35,
      head: [["Symbol", "Type", "Entry", "Exit", "P&L", "Status", "Date"]],
      body: filteredTrades.map((trade) => [
        trade.symbol,
        trade.trade_type,
        `$${trade.entry_price.toFixed(2)}`,
        trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : "N/A",
        trade.profit_loss ? `$${trade.profit_loss.toFixed(2)}` : "$0.00",
        trade.status,
        format(new Date(trade.opened_at), "MMM dd, yyyy"),
      ]),
      styles: { fontSize: 9 },
      headStyles: { fillColor: [59, 130, 246] },
    });

    doc.save(`trades-report-${format(new Date(), "yyyy-MM-dd")}.pdf`);
  };

  const hasActiveFilters = dateRange.from || dateRange.to || symbolFilter || (statusFilter && statusFilter !== "all");

  return (
    <Card className="p-3 sm:p-4 md:p-6 border-border/50 bg-card/50 backdrop-blur-sm w-full min-w-0">
      <CardHeader className="px-0 pt-0 pb-3 sm:pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-lg sm:text-xl font-semibold">Trade History</CardTitle>
            <CardDescription className="mt-1 text-xs sm:text-sm">
              {filteredTrades.length} {filteredTrades.length === 1 ? "trade" : "trades"} found
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant={showFilters ? "default" : "outline"}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
              className="text-xs sm:text-sm"
            >
              <Filter className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
              Filters
              {hasActiveFilters && (
                <Badge variant="secondary" className="ml-1 sm:ml-2 px-1 min-w-[20px] text-xs">
                  {[dateRange.from, dateRange.to, symbolFilter, statusFilter !== "all"].filter(Boolean).length}
                </Badge>
              )}
            </Button>
            <Button variant="outline" size="sm" onClick={exportToCSV} className="text-xs sm:text-sm">
              <FileText className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
              CSV
            </Button>
            <Button variant="outline" size="sm" onClick={exportToPDF} className="text-xs sm:text-sm">
              <Download className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
              PDF
            </Button>
          </div>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="mt-3 sm:mt-4 p-3 sm:p-4 rounded-lg border border-border/50 bg-muted/20 space-y-3 sm:space-y-4 animate-fade-in">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
              {/* Date Range */}
              <div className="space-y-2">
                <Label>Date Range</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className={cn(
                        "w-full justify-start text-left font-normal",
                        !dateRange.from && "text-muted-foreground"
                      )}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {dateRange.from ? (
                        dateRange.to ? (
                          <>
                            {format(dateRange.from, "MMM dd")} - {format(dateRange.to, "MMM dd")}
                          </>
                        ) : (
                          format(dateRange.from, "MMM dd, yyyy")
                        )
                      ) : (
                        <span>Pick a date</span>
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="range"
                      selected={{ from: dateRange.from, to: dateRange.to }}
                      onSelect={(range: DateRange | undefined) => setDateRange(range || {})}
                      numberOfMonths={2}
                      className="pointer-events-auto"
                    />
                  </PopoverContent>
                </Popover>
              </div>

              {/* Symbol Search */}
              <div className="space-y-2">
                <Label htmlFor="symbol">Symbol</Label>
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="symbol"
                    placeholder="Search symbol..."
                    value={symbolFilter}
                    onChange={(e) => setSymbolFilter(e.target.value)}
                    className="pl-8"
                  />
                </div>
              </div>

              {/* Status Filter */}
              <div className="space-y-2">
                <Label htmlFor="status">Status</Label>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger id="status">
                    <SelectValue placeholder="All statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="executed">Executed</SelectItem>
                    <SelectItem value="closed">Closed</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Clear Filters */}
              <div className="space-y-2">
                <Label>&nbsp;</Label>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={clearFilters}
                  disabled={!hasActiveFilters}
                >
                  <X className="w-4 h-4 mr-2" />
                  Clear
                </Button>
              </div>
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent className="px-0 pb-0">
        {filteredTrades.length === 0 ? (
          <div className="text-center py-8 sm:py-12">
            <div className="w-12 h-12 sm:w-16 sm:h-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-3 sm:mb-4">
              <ArrowUpRight className="w-6 h-6 sm:w-8 sm:h-8 text-muted-foreground" />
            </div>
            <p className="text-sm sm:text-base text-muted-foreground px-4">
              {hasActiveFilters ? "No trades match your filters" : "No trades yet. Start a strategy to begin trading."}
            </p>
          </div>
        ) : (
          <ScrollArea className="h-[600px] px-4">
            <div className="space-y-2 pr-4">
              {filteredTrades.map((trade) => (
                <div
                  key={trade.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between p-3 sm:p-4 rounded-lg border border-border/50 hover:bg-muted/30 transition-all duration-200 group gap-2 sm:gap-4 min-w-0"
                >
                  <div className="flex items-center gap-3 sm:gap-4 flex-1 min-w-0">
                    {trade.profit_loss && trade.profit_loss >= 0 ? (
                      <div className="w-8 h-8 sm:w-10 sm:h-10 md:w-11 md:h-11 rounded-xl bg-success/10 flex items-center justify-center group-hover:bg-success/20 transition-colors flex-shrink-0">
                        <ArrowUpRight className="w-4 h-4 sm:w-5 sm:h-5 text-success" />
                      </div>
                    ) : (
                      <div className="w-8 h-8 sm:w-10 sm:h-10 md:w-11 md:h-11 rounded-xl bg-destructive/10 flex items-center justify-center group-hover:bg-destructive/20 transition-colors flex-shrink-0">
                        <ArrowDownRight className="w-4 h-4 sm:w-5 sm:h-5 text-destructive" />
                      </div>
                    )}

                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-sm sm:text-base text-foreground group-hover:text-primary transition-colors truncate">
                        {trade.symbol}
                      </div>
                      <div className="text-xs sm:text-sm text-muted-foreground flex items-center gap-1 sm:gap-2 flex-wrap">
                        <span className="font-medium">{trade.trade_type}</span>
                        <span className="hidden sm:inline">•</span>
                        <span className="text-xs">{new Date(trade.opened_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
                      </div>
                      {/* Why the bot took this trade, from metadata.why */}
                      <TradeReasoning
                        why={
                          (trade.metadata as { why?: TradeWhy } | null)?.why ?? null
                        }
                      />
                      {/* Why it ENDED that way -- the diagnosis, not just "SL" */}
                      <TradeOutcomeReasoning
                        outcome={(trade.metadata as TradeOutcome | null) ?? null}
                      />
                    </div>
                  </div>

                  <div className="flex sm:flex-row items-center justify-between sm:justify-end gap-2 sm:gap-3 border-t sm:border-t-0 sm:border-l border-border/30 pt-2 sm:pt-0 sm:pl-3">
                    <div className="flex-1 sm:flex-initial sm:text-right">
                      {trade.profit_loss && (
                        <div
                          className={`text-base sm:text-lg font-bold ${
                            trade.profit_loss >= 0
                              ? "text-success"
                              : "text-destructive"
                          }`}
                        >
                          {trade.profit_loss >= 0 ? "+" : ""}
                          ${trade.profit_loss.toFixed(2)}
                        </div>
                      )}
                      <Badge
                        variant={trade.status === "executed" ? "default" : "secondary"}
                        className="min-w-[60px] sm:min-w-[80px] justify-center text-xs mt-1"
                      >
                        {trade.status}
                      </Badge>
                    </div>
                    <div className="flex gap-2">
                      <TradeJournalDialog tradeId={trade.id} />
                      <ShareableTradeCard trade={trade} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
};
