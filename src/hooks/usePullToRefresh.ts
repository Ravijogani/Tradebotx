import { useEffect, useRef, useState } from 'react';

interface PullToRefreshOptions {
  onRefresh: () => Promise<void>;
  threshold?: number;
  maxPullDistance?: number;
}

export const usePullToRefresh = ({
  onRefresh,
  threshold = 80,
  maxPullDistance = 150
}: PullToRefreshOptions) => {
  const ref = useRef<HTMLDivElement>(null);
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [startY, setStartY] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    let isPulling = false;

    const handleTouchStart = (e: TouchEvent) => {
      // Only start if scrolled to top
      if (element.scrollTop === 0) {
        setStartY(e.touches[0].clientY);
        isPulling = true;
      }
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!isPulling || isRefreshing) return;

      const currentY = e.touches[0].clientY;
      const distance = Math.min(currentY - startY, maxPullDistance);

      if (distance > 0) {
        e.preventDefault();
        setPullDistance(distance);
      }
    };

    const handleTouchEnd = async () => {
      if (!isPulling) return;
      isPulling = false;

      if (pullDistance >= threshold && !isRefreshing) {
        setIsRefreshing(true);
        try {
          await onRefresh();
        } finally {
          setIsRefreshing(false);
          setPullDistance(0);
        }
      } else {
        setPullDistance(0);
      }
    };

    element.addEventListener('touchstart', handleTouchStart, { passive: true });
    element.addEventListener('touchmove', handleTouchMove, { passive: false });
    element.addEventListener('touchend', handleTouchEnd);

    return () => {
      element.removeEventListener('touchstart', handleTouchStart);
      element.removeEventListener('touchmove', handleTouchMove);
      element.removeEventListener('touchend', handleTouchEnd);
    };
  }, [startY, pullDistance, threshold, maxPullDistance, isRefreshing, onRefresh]);

  return {
    ref,
    pullDistance,
    isRefreshing,
    pullProgress: Math.min(pullDistance / threshold, 1)
  };
};
