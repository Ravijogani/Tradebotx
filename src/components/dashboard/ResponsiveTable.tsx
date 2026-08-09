import { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ResponsiveTableProps {
  children: ReactNode;
  className?: string;
}

/**
 * Responsive table wrapper that handles overflow on mobile devices
 * Use this for any table-like content that needs horizontal scrolling
 */
export const ResponsiveTable = ({ children, className = "" }: ResponsiveTableProps) => {
  return (
    <div className={`w-full ${className}`}>
      {/* Desktop: normal table */}
      <div className="hidden md:block overflow-x-auto">
        {children}
      </div>
      
      {/* Mobile: scrollable with touch-friendly */}
      <ScrollArea className="md:hidden w-full">
        <div className="min-w-[600px]">
          {children}
        </div>
      </ScrollArea>
    </div>
  );
};

/**
 * Responsive card list for mobile - converts tables to stacked cards
 */
interface ResponsiveCardListProps<T> {
  items: T[];
  renderCard: (item: T, index: number) => ReactNode;
  renderTable: () => ReactNode;
}

export const ResponsiveCardList = <T,>({ items, renderCard, renderTable }: ResponsiveCardListProps<T>) => {
  return (
    <>
      {/* Desktop: Table view */}
      <div className="hidden md:block">
        {renderTable()}
      </div>
      
      {/* Mobile: Card view */}
      <div className="md:hidden space-y-3">
        {items.map((item, index) => renderCard(item, index))}
      </div>
    </>
  );
};