import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Bell, Loader2, Check, X, Send } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface TelegramNotificationSettingsProps {
  userId: string;
}

export const TelegramNotificationSettings = ({ userId }: TelegramNotificationSettingsProps) => {
  const [telegramChatId, setTelegramChatId] = useState("");
  const [isEnabled, setIsEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [testingSend, setTestingSend] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadTelegramSettings();
  }, [userId]);

  const loadTelegramSettings = async () => {
    try {
      const { data } = await supabase
        .from("user_setup")
        .select("telegram_chat_id")
        .eq("user_id", userId)
        .single();

      if (data && data.telegram_chat_id) {
        setTelegramChatId(data.telegram_chat_id);
        setIsEnabled(true);
      }
    } catch (error) {
      console.error("Error loading telegram settings:", error);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const { error } = await supabase
        .from("user_setup")
        .update({ telegram_chat_id: telegramChatId || null })
        .eq("user_id", userId);

      if (error) throw error;

      setIsEnabled(!!telegramChatId);
      toast({
        title: "Telegram settings saved",
        description: telegramChatId
          ? "Telegram notifications are now enabled"
          : "Telegram notifications are disabled",
      });
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

  const handleTestNotification = async () => {
    if (!telegramChatId) {
      toast({
        title: "Chat ID required",
        description: "Please save your Telegram Chat ID first",
        variant: "destructive",
      });
      return;
    }

    setTestingSend(true);
    try {
      const { error } = await supabase.functions.invoke('send-telegram-notification', {
        body: {
          chatId: telegramChatId,
          message: `🔔 Test Notification\n\nThis is a test message from TradeBotX.\n\nIf you received this, your Telegram notifications are working correctly! 🎉`,
        }
      });

      if (error) throw error;

      toast({
        title: "Test notification sent!",
        description: "Check your Telegram to confirm receipt",
      });
    } catch (error: any) {
      toast({
        title: "Test failed",
        description: error.message || "Failed to send test notification",
        variant: "destructive",
      });
    } finally {
      setTestingSend(false);
    }
  };

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Bell className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <CardTitle>Telegram Notifications</CardTitle>
              <CardDescription>Get real-time alerts on Telegram</CardDescription>
            </div>
          </div>
          <Badge
            variant={isEnabled ? "default" : "secondary"}
            className={isEnabled ? "bg-success/20 text-success border-success/30" : ""}
          >
            {isEnabled ? (
              <>
                <Check className="w-3 h-3 mr-1" />
                Enabled
              </>
            ) : (
              <>
                <X className="w-3 h-3 mr-1" />
                Disabled
              </>
            )}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2">
          <Label htmlFor="telegram_chat_id">Telegram Chat ID</Label>
          <Input
            id="telegram_chat_id"
            placeholder="Enter your Telegram Chat ID"
            value={telegramChatId}
            onChange={(e) => setTelegramChatId(e.target.value)}
            className="bg-background/50"
            aria-describedby="telegram-hint"
          />
          <p id="telegram-hint" className="text-xs text-muted-foreground">
            To get your Chat ID, message{" "}
            <a
              href="https://t.me/userinfobot"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              @userinfobot
            </a>{" "}
            on Telegram
          </p>
        </div>

        <div className="p-3 rounded-lg bg-muted/50 border border-border/50">
          <h4 className="text-sm font-medium mb-2">What you'll receive:</h4>
          <ul className="text-sm text-muted-foreground space-y-1">
            <li className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              Bot start/stop notifications
            </li>
            <li className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              Trade execution alerts
            </li>
            <li className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              Trade close notifications with P&L
            </li>
            <li className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              Critical system alerts
            </li>
          </ul>
        </div>

        <div className="flex gap-2">
          <Button onClick={handleSave} disabled={loading} className="flex-1">
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              "Save Settings"
            )}
          </Button>
          <Button
            variant="outline"
            onClick={handleTestNotification}
            disabled={!telegramChatId || testingSend}
            aria-label="Send test notification"
          >
            {testingSend ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};