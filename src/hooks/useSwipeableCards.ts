import { useState, useRef, useCallback } from 'react';

interface UseSwipeableCardsProps {
  totalCards: number;
  onCardChange?: (index: number) => void;
}

export const useSwipeableCards = ({ totalCards, onCardChange }: UseSwipeableCardsProps) => {
  const [currentCard, setCurrentCard] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [startX, setStartX] = useState(0);
  const [currentX, setCurrentX] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const goToCard = useCallback((index: number) => {
    if (index >= 0 && index < totalCards) {
      setCurrentCard(index);
      onCardChange?.(index);
    }
  }, [totalCards, onCardChange]);

  const handleTouchStart = (e: React.TouchEvent) => {
    setIsDragging(true);
    setStartX(e.touches[0].clientX);
    setCurrentX(e.touches[0].clientX);
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
    isDragging
  };
};
