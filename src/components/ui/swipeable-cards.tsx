import React from 'react';
import { useSwipeableCards } from '@/hooks/useSwipeableCards';
import { cn } from '@/lib/utils';

interface SwipeableCardsProps {
  children: React.ReactNode[];
  className?: string;
  showIndicators?: boolean;
  onCardChange?: (index: number) => void;
}

export const SwipeableCards: React.FC<SwipeableCardsProps> = ({
  children,
  className,
  showIndicators = true,
  onCardChange
}) => {
  const {
    currentCard,
    goToCard,
    containerRef,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
    getTransform,
    isDragging
  } = useSwipeableCards({
    totalCards: children.length,
    onCardChange
  });

  return (
    <div className={cn("relative w-full overflow-hidden", className)}>
      {/* Cards Container */}
      <div
        ref={containerRef}
        className="flex touch-pan-y"
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        style={{
          transform: getTransform(),
          transition: isDragging ? 'none' : 'transform 0.3s ease-out'
        }}
      >
        {children.map((child, index) => (
          <div
            key={index}
            className="flex-shrink-0 w-full px-4"
            style={{ width: '100%' }}
          >
            {child}
          </div>
        ))}
      </div>

      {/* Pagination Dots */}
      {showIndicators && children.length > 1 && (
        <div className="flex justify-center items-center gap-2 mt-6">
          {children.map((_, index) => (
            <button
              key={index}
              onClick={() => goToCard(index)}
              className={cn(
                "h-2 rounded-full transition-all duration-300",
                index === currentCard
                  ? "w-8 bg-primary"
                  : "w-2 bg-muted-foreground/30 hover:bg-muted-foreground/50"
              )}
              aria-label={`Go to slide ${index + 1}`}
            />
          ))}
        </div>
      )}

      {/* Navigation Hints (subtle) */}
      {children.length > 1 && (
        <>
          {currentCard > 0 && (
            <div className="absolute left-2 top-1/2 -translate-y-1/2 opacity-30 pointer-events-none">
              <div className="w-8 h-8 rounded-full bg-background/80 backdrop-blur-sm flex items-center justify-center">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </div>
            </div>
          )}
          {currentCard < children.length - 1 && (
            <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-30 pointer-events-none">
              <div className="w-8 h-8 rounded-full bg-background/80 backdrop-blur-sm flex items-center justify-center">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
