import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { cn } from "@/lib/utils";
import { TradeJournalDialog } from "./TradeJournalDialog";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

export const TradesListEnhanced = () => {
  const [trades, setTrades] = useState<any[]>([]);
  const [filteredTrades, setFilteredTrades] = useState<any[]>([]);
  const [dateRange, setDateRange] = useState<{ from?: Date; to?: Date }>({});
  const [symbolFilter, setSymbolFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    loadTrades();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [trades, dateRange, symbolFilter, statusFilter]);

  const loadTrades = async () => {
    const { data } = await supabase
      .from("trades")
      .select("*")
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
      parseFloat(trade.entry_price).toFixed(2),
      trade.exit_price ? parseFloat(trade.exit_price).toFixed(2) : "N/A",
      trade.profit_loss ? parseFloat(trade.profit_loss).toFixed(2) : "0.00",
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
        `$${parseFloat(trade.entry_price).toFixed(2)}`,
        trade.exit_price ? `$${parseFloat(trade.exit_price).toFixed(2)}` : "N/A",
        trade.profit_loss ? `$${parseFloat(trade.profit_loss).toFixed(2)}` : "$0.00",
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
    <Card className="p-6 border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader className="px-0 pt-0">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-xl font-semibold">Trade History</CardTitle>
            <CardDescription className="mt-1">
              {filteredTrades.length} {filteredTrades.length === 1 ? "trade" : "trades"} found
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={showFilters ? "default" : "outline"}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-4 h-4 mr-2" />
              Filters
              {hasActiveFilters && (
                <Badge variant="secondary" className="ml-2 px-1 min-w-[20px]">
                  {[dateRange.from, dateRange.to, symbolFilter, statusFilter !== "all"].filter(Boolean).length}
                </Badge>
              )}
            </Button>
            <Button variant="outline" size="sm" onClick={exportToCSV}>
              <FileText className="w-4 h-4 mr-2" />
              CSV
            </Button>
            <Button variant="outline" size="sm" onClick={exportToPDF}>
              <Download className="w-4 h-4 mr-2" />
              PDF
            </Button>
          </div>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="mt-4 p-4 rounded-lg border border-border/50 bg-muted/20 space-y-4 animate-fade-in">
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
                      onSelect={(range: any) => setDateRange(range || {})}
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
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
              <ArrowUpRight className="w-8 h-8 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground">
              {hasActiveFilters ? "No trades match your filters" : "No trades yet. Start a strategy to begin trading."}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredTrades.map((trade) => (
              <div
                key={trade.id}
                className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:bg-muted/30 transition-all duration-200 group"
              >
                <div className="flex items-center gap-4 flex-1">
                  {trade.profit_loss && parseFloat(trade.profit_loss) >= 0 ? (
                    <div className="w-11 h-11 rounded-xl bg-success/10 flex items-center justify-center group-hover:bg-success/20 transition-colors">
                      <ArrowUpRight className="w-5 h-5 text-success" />
                    </div>
                  ) : (
                    <div className="w-11 h-11 rounded-xl bg-destructive/10 flex items-center justify-center group-hover:bg-destructive/20 transition-colors">
                      <ArrowDownRight className="w-5 h-5 text-destructive" />
                    </div>
                  )}

                  <div className="flex-1">
                    <div className="font-semibold text-foreground group-hover:text-primary transition-colors">
                      {trade.symbol}
                    </div>
                    <div className="text-sm text-muted-foreground flex items-center gap-2">
                      <span className="font-medium">{trade.trade_type}</span>
                      <span>•</span>
                      <span>{new Date(trade.opened_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    {trade.profit_loss && (
                      <div
                        className={`text-lg font-bold ${
                          parseFloat(trade.profit_loss) >= 0
                            ? "text-success"
                            : "text-destructive"
                        }`}
                      >
                        {parseFloat(trade.profit_loss) >= 0 ? "+" : ""}
                        ${parseFloat(trade.profit_loss).toFixed(2)}
                      </div>
                    )}
                    <Badge
                      variant={trade.status === "executed" ? "default" : "secondary"}
                      className="min-w-[80px] justify-center"
                    >
                      {trade.status}
                    </Badge>
                  </div>
                  <TradeJournalDialog tradeId={trade.id} />
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
