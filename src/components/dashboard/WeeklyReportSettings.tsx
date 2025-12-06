import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { Mail, Calendar, Clock, Loader2, CheckCircle } from "lucide-react";
import { format } from "date-fns";

interface ReportSettings {
  id: string;
  is_enabled: boolean;
  send_day: string;
  last_sent_at: string | null;
}

const days = [
  { value: "monday", label: "Monday" },
  { value: "tuesday", label: "Tuesday" },
  { value: "wednesday", label: "Wednesday" },
  { value: "thursday", label: "Thursday" },
  { value: "friday", label: "Friday" },
  { value: "saturday", label: "Saturday" },
  { value: "sunday", label: "Sunday" }
];

export const WeeklyReportSettings = () => {
  const [settings, setSettings] = useState<ReportSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const { data, error } = await supabase
        .from("weekly_report_settings")
        .select("*")
        .eq("user_id", user.id)
        .single();

      if (error && error.code !== "PGRST116") throw error;

      if (data) {
        setSettings(data);
      } else {
        // Create default settings
        const { data: newSettings, error: createError } = await supabase
          .from("weekly_report_settings")
          .insert({ user_id: user.id })
          .select()
          .single();

        if (createError) throw createError;
        setSettings(newSettings);
      }
    } catch (error: any) {
      toast({
        title: "Error loading settings",
        description: error.message,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const updateSettings = async (updates: Partial<ReportSettings>) => {
    if (!settings) return;
    setSaving(true);

    try {
      const { error } = await supabase
        .from("weekly_report_settings")
        .update(updates)
        .eq("id", settings.id);

      if (error) throw error;

      setSettings({ ...settings, ...updates });
      toast({ title: "Settings updated" });
    } catch (error: any) {
      toast({
        title: "Error updating settings",
        description: error.message,
        variant: "destructive"
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Mail className="h-5 w-5" />
          Weekly Email Reports
        </CardTitle>
        <CardDescription>
          Receive automated weekly P&L summaries via email
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between p-4 rounded-lg border border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <Mail className="h-5 w-5 text-primary" />
            </div>
            <div>
              <Label className="text-base font-medium">Weekly Reports</Label>
              <p className="text-sm text-muted-foreground">
                Get a detailed performance summary every week
              </p>
            </div>
          </div>
          <Switch
            checked={settings?.is_enabled ?? true}
            onCheckedChange={(checked) => updateSettings({ is_enabled: checked })}
            disabled={saving}
          />
        </div>

        {/* Send Day Selection */}
        {settings?.is_enabled && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <Label>Delivery Day</Label>
            </div>
            <Select
              value={settings?.send_day ?? "monday"}
              onValueChange={(value) => updateSettings({ send_day: value })}
              disabled={saving}
            >
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Select day" />
              </SelectTrigger>
              <SelectContent>
                {days.map((day) => (
                  <SelectItem key={day.value} value={day.value}>
                    {day.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Reports are sent at 9:00 AM UTC
            </p>
          </div>
        )}

        {/* Report Preview */}
        {settings?.is_enabled && (
          <div className="p-4 rounded-lg bg-muted/50 border border-dashed border-border">
            <h4 className="font-medium mb-2">What's included in your report:</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-success" />
                Weekly P&L summary with percentage change
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-success" />
                Trade count and win rate
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-success" />
                Best and worst performing symbols
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-success" />
                Account balance and equity changes
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-success" />
                Bot uptime and performance metrics
              </li>
            </ul>
          </div>
        )}

        {/* Last Sent */}
        {settings?.last_sent_at && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            Last report sent: {format(new Date(settings.last_sent_at), "MMMM d, yyyy 'at' h:mm a")}
          </div>
        )}
      </CardContent>
    </Card>
  );
};