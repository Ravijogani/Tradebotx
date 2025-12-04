import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Clock, RefreshCw } from "lucide-react";

interface SessionTimeoutWarningProps {
  warningThresholdMinutes?: number; // Show warning when this many minutes left
  onSessionRefresh?: () => void;
}

export const SessionTimeoutWarning = ({ 
  warningThresholdMinutes = 5,
  onSessionRefresh 
}: SessionTimeoutWarningProps) => {
  const [showWarning, setShowWarning] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    const checkSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      
      if (session?.expires_at) {
        const expiresAt = new Date(session.expires_at * 1000);
        const now = new Date();
        const diffMinutes = (expiresAt.getTime() - now.getTime()) / (1000 * 60);
        
        setTimeRemaining(Math.floor(diffMinutes));
        
        if (diffMinutes <= warningThresholdMinutes && diffMinutes > 0) {
          setShowWarning(true);
        } else {
          setShowWarning(false);
        }
        
        // Auto refresh if less than 2 minutes remaining
        if (diffMinutes <= 2 && diffMinutes > 0) {
          handleRefreshSession();
        }
      }
    };

    // Check immediately
    checkSession();

    // Check every minute
    const interval = setInterval(checkSession, 60000);

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        if (session?.expires_at) {
          const expiresAt = new Date(session.expires_at * 1000);
          const now = new Date();
          const diffMinutes = (expiresAt.getTime() - now.getTime()) / (1000 * 60);
          setTimeRemaining(Math.floor(diffMinutes));
          setShowWarning(diffMinutes <= warningThresholdMinutes && diffMinutes > 0);
        }
      }
    );

    return () => {
      clearInterval(interval);
      subscription.unsubscribe();
    };
  }, [warningThresholdMinutes]);

  const handleRefreshSession = async () => {
    setIsRefreshing(true);
    try {
      const { data, error } = await supabase.auth.refreshSession();
      
      if (error) throw error;
      
      if (data.session) {
        setShowWarning(false);
        toast({
          title: "Session Refreshed",
          description: "Your session has been extended.",
        });
        onSessionRefresh?.();
      }
    } catch (error: any) {
      toast({
        title: "Session Refresh Failed",
        description: "Please log in again.",
        variant: "destructive",
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  if (!showWarning) return null;

  return (
    <Alert className="fixed bottom-4 right-4 w-auto max-w-sm z-50 border-warning bg-warning/10 animate-fade-in shadow-lg">
      <Clock className="h-4 w-4 text-warning" />
      <AlertDescription className="flex items-center justify-between gap-4">
        <span className="text-sm">
          Session expires in {timeRemaining} minute{timeRemaining !== 1 ? 's' : ''}
        </span>
        <Button
          size="sm"
          variant="outline"
          onClick={handleRefreshSession}
          disabled={isRefreshing}
          className="shrink-0"
        >
          {isRefreshing ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            "Extend"
          )}
        </Button>
      </AlertDescription>
    </Alert>
  );
};
