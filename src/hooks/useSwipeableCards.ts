import { useState, useRef, useCallback, useEffect } from 'react';

interface UseSwipeableCardsProps {
  totalCards: number;
  onCardChange?: (index: number) => void;
  autoplay?: boolean;
  autoplayInterval?: number;
}

export const useSwipeableCards = ({ 
  totalCards, 
  onCardChange,
  autoplay = false,
  autoplayInterval = 5000
}: UseSwipeableCardsProps) => {
  const [currentCard, setCurrentCard] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [startX, setStartX] = useState(0);
  const [currentX, setCurrentX] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const autoplayTimerRef = useRef<NodeJS.Timeout | null>(null);

  const goToCard = useCallback((index: number) => {
    if (index >= 0 && index < totalCards) {
      setCurrentCard(index);
      onCardChange?.(index);
    }
  }, [totalCards, onCardChange]);

  // Autoplay effect
  useEffect(() => {
    if (!autoplay || isPaused || totalCards <= 1) return;

    autoplayTimerRef.current = setInterval(() => {
      setCurrentCard((prev) => (prev + 1) % totalCards);
    }, autoplayInterval);

    return () => {
      if (autoplayTimerRef.current) {
        clearInterval(autoplayTimerRef.current);
      }
    };
  }, [autoplay, isPaused, totalCards, autoplayInterval]);

  const pauseAutoplay = useCallback(() => {
    setIsPaused(true);
    if (autoplayTimerRef.current) {
      clearInterval(autoplayTimerRef.current);
    }
  }, []);

  const resumeAutoplay = useCallback(() => {
    setIsPaused(false);
  }, []);

  const handleTouchStart = (e: React.TouchEvent) => {
    setIsDragging(true);
    setStartX(e.touches[0].clientX);
    setCurrentX(e.touches[0].clientX);
    pauseAutoplay();
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (!isDragging) return;
    setCurrentX(e.touches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (!isDragging) return;
    
    const diff = startX - currentX;
    const threshold = 50; // Minimum swipe distance

    if (Math.abs(diff) > threshold) {
      if (diff > 0 && currentCard < totalCards - 1) {
        // Swipe left - next card
        goToCard(currentCard + 1);
      } else if (diff < 0 && currentCard > 0) {
        // Swipe right - previous card
        goToCard(currentCard - 1);
      }
    }

    setIsDragging(false);
    setStartX(0);
    setCurrentX(0);
    
    // Resume autoplay after a delay
    setTimeout(() => {
      resumeAutoplay();
    }, 1000);
  };

  const getTransform = () => {
    const offset = -currentCard * 100;
    if (isDragging && startX !== 0) {
      const dragOffset = ((currentX - startX) / (containerRef.current?.offsetWidth || 1)) * 100;
      return `translateX(calc(${offset}% + ${dragOffset}%))`;
    }
    return `translateX(${offset}%)`;
  };

  return {
    currentCard,
    goToCard,
    containerRef,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
    getTransform,
    isDragging,
    pauseAutoplay,
    resumeAutoplay,
    isPaused
  };
};
