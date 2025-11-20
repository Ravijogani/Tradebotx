import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, Download, Loader2, TrendingUp, TrendingDown } from "lucide-react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { format, subDays, startOfDay, endOfDay } from "date-fns";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import SymbolPerformanceChart from "@/components/dashboard/SymbolPerformanceChart";
import RiskMetricsCard from "@/components/dashboard/RiskMetricsCard";
import WithdrawalMilestones from "@/components/dashboard/WithdrawalMilestones";

const PLReports = () => {
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState("30");
  const [stats, setStats] = useState({
    totalPL: 0,
    winRate: 0,
    totalTrades: 0,
    avgProfit: 0,
  });
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    checkAuthAndLoadData();
  }, [dateRange]);

  const checkAuthAndLoadData = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      
      if (!session) {
        navigate("/auth/login");
        return;
      }

      await loadTrades(session.user.id);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadTrades = async (userId: string) => {
    const daysAgo = parseInt(dateRange);
    const startDate = startOfDay(subDays(new Date(), daysAgo));
    
    const { data, error } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", userId)
      .gte("opened_at", startDate.toISOString())
      .order("opened_at", { ascending: true });

    if (error) throw error;

    setTrades(data || []);
    calculateStats(data || []);
  };

  const calculateStats = (tradesData: any[]) => {
    const completedTrades = tradesData.filter(t => t.status === 'closed' && t.profit_loss !== null);
    
    const totalPL = completedTrades.reduce((sum, t) => sum + Number(t.profit_loss || 0), 0);
    const winningTrades = completedTrades.filter(t => Number(t.profit_loss) > 0);
    const winRate = completedTrades.length > 0 ? (winningTrades.length / completedTrades.length) * 100 : 0;
    const avgProfit = completedTrades.length > 0 ? totalPL / completedTrades.length : 0;

    setStats({
      totalPL,
      winRate,
      totalTrades: completedTrades.length,
      avgProfit,
    });
  };

  const getChartData = () => {
    const completedTrades = trades.filter(t => t.status === 'closed' && t.profit_loss !== null);
    let cumulativePL = 0;
    
    return completedTrades.map(trade => {
      cumulativePL += Number(trade.profit_loss || 0);
      return {
        date: format(new Date(trade.closed_at), "MMM dd"),
        pl: Number(trade.profit_loss || 0),
        cumulative: cumulativePL,
        symbol: trade.symbol,
      };
    });
  };

  const exportToPDF = () => {
    const doc = new jsPDF();
    
    // Add branding header
    doc.setFontSize(20);
    doc.setTextColor(79, 70, 229); // Primary color
    doc.text("TradeBotX Platform", 14, 20);
    
    doc.setFontSize(16);
    doc.setTextColor(0, 0, 0);
    doc.text("P&L Report", 14, 30);
    
    doc.setFontSize(10);
    doc.text(`Generated: ${format(new Date(), "MMM dd, yyyy HH:mm")}`, 14, 38);
    doc.text(`Period: Last ${dateRange} days`, 14, 44);
    
    // Add summary stats
    doc.setFontSize(12);
    doc.text("Summary Statistics", 14, 55);
    
    const summaryData = [
      ["Total P&L", `₹${stats.totalPL.toFixed(2)}`],
      ["Total Trades", stats.totalTrades.toString()],
      ["Win Rate", `${stats.winRate.toFixed(2)}%`],
      ["Avg Profit/Trade", `₹${stats.avgProfit.toFixed(2)}`],
    ];
    
    autoTable(doc, {
      startY: 60,
      head: [["Metric", "Value"]],
      body: summaryData,
      theme: "grid",
      headStyles: { fillColor: [59, 130, 246] },
    });
    
    // Add trades table
    const completedTrades = trades.filter(t => t.status === 'closed' && t.profit_loss !== null);
    const tradesData = completedTrades.map(trade => [
      format(new Date(trade.opened_at), "MMM dd, yyyy"),
      trade.symbol,
      trade.trade_type,
      `₹${Number(trade.entry_price).toFixed(2)}`,
      `₹${Number(trade.exit_price).toFixed(2)}`,
      `₹${Number(trade.profit_loss).toFixed(2)}`,
    ]);
    
    autoTable(doc, {
      startY: (doc as any).lastAutoTable.finalY + 15,
      head: [["Date", "Symbol", "Type", "Entry", "Exit", "P&L"]],
      body: tradesData,
      theme: "striped",
      headStyles: { fillColor: [59, 130, 246] },
    });
    
    // Add footer
    const pageCount = (doc as any).internal.getNumberOfPages();
    doc.setFontSize(8);
    doc.setTextColor(128, 128, 128);
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.text(
        `TradeBotX Platform - Confidential | Page ${i} of ${pageCount}`,
        doc.internal.pageSize.getWidth() / 2,
        doc.internal.pageSize.getHeight() - 10,
        { align: "center" }
      );
    }
    
    doc.save(`pl-report-${format(new Date(), "yyyy-MM-dd")}.pdf`);
    
    toast({
      title: "Success",
      description: "P&L report exported successfully",
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  const chartData = getChartData();

  return (
    <div className="min-h-screen bg-background p-4 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate("/dashboard")}>
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-3xl font-bold">P&L Reports</h1>
              <p className="text-muted-foreground">Detailed profit and loss analytics</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Select value={dateRange} onValueChange={setDateRange}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="30">Last 30 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
                <SelectItem value="365">Last year</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={exportToPDF}>
              <Download className="w-4 h-4 mr-2" />
              Export PDF
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
              {stats.totalPL >= 0 ? (
                <TrendingUp className="h-4 w-4 text-green-500" />
              ) : (
                <TrendingDown className="h-4 w-4 text-red-500" />
              )}
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${stats.totalPL >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ₹{stats.totalPL.toFixed(2)}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Win Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.winRate.toFixed(2)}%</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Trades</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalTrades}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Profit/Trade</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${stats.avgProfit >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ₹{stats.avgProfit.toFixed(2)}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        {chartData.length > 0 ? (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Cumulative P&L</CardTitle>
                <CardDescription>Your cumulative profit/loss over time</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line 
                      type="monotone" 
                      dataKey="cumulative" 
                      stroke="hsl(var(--primary))" 
                      strokeWidth={2}
                      name="Cumulative P&L"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Trade-by-Trade P&L</CardTitle>
                <CardDescription>Individual trade performance</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar 
                      dataKey="pl" 
                      fill="hsl(var(--primary))"
                      name="P&L per Trade"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </>
        ) : (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <p className="text-muted-foreground mb-4">No trade data available for the selected period</p>
              <Button onClick={() => navigate("/dashboard")}>
                Back to Dashboard
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Withdrawal Milestones */}
        <WithdrawalMilestones />

        {/* Advanced Risk Metrics */}
        <RiskMetricsCard />

        {/* Symbol Performance */}
        <SymbolPerformanceChart />
      </div>
    </div>
  );
};

export default PLReports;
