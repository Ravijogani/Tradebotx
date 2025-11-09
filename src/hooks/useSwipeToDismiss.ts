import { useEffect, useRef, useState } from 'react';

interface SwipeToDismissOptions {
  onDismiss: () => void;
  threshold?: number;
  direction?: 'right' | 'down' | 'left' | 'up';
}

export const useSwipeToDismiss = ({
  onDismiss,
  threshold = 100,
  direction = 'down'
}: SwipeToDismissOptions) => {
  const ref = useRef<HTMLDivElement>(null);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [currentPos, setCurrentPos] = useState({ x: 0, y: 0 });
  const [isSwiping, setIsSwiping] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const handleTouchStart = (e: TouchEvent) => {
      const touch = e.touches[0];
      setStartPos({ x: touch.clientX, y: touch.clientY });
      setCurrentPos({ x: touch.clientX, y: touch.clientY });
      setIsSwiping(true);
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!isSwiping) return;
      const touch = e.touches[0];
      setCurrentPos({ x: touch.clientX, y: touch.clientY });

      const deltaX = touch.clientX - startPos.x;
      const deltaY = touch.clientY - startPos.y;

      // Apply transform for visual feedback
      if (direction === 'down' && deltaY > 0) {
        element.style.transform = `translateY(${deltaY}px)`;
        element.style.opacity = String(1 - Math.min(deltaY / threshold / 2, 0.5));
      } else if (direction === 'right' && deltaX > 0) {
        element.style.transform = `translateX(${deltaX}px)`;
        element.style.opacity = String(1 - Math.min(deltaX / threshold / 2, 0.5));
      } else if (direction === 'left' && deltaX < 0) {
        element.style.transform = `translateX(${deltaX}px)`;
        element.style.opacity = String(1 - Math.min(Math.abs(deltaX) / threshold / 2, 0.5));
      } else if (direction === 'up' && deltaY < 0) {
        element.style.transform = `translateY(${deltaY}px)`;
        element.style.opacity = String(1 - Math.min(Math.abs(deltaY) / threshold / 2, 0.5));
      }
    };

    const handleTouchEnd = () => {
      if (!isSwiping) return;

      const deltaX = currentPos.x - startPos.x;
      const deltaY = currentPos.y - startPos.y;

      let shouldDismiss = false;

      if (direction === 'down' && deltaY > threshold) {
        shouldDismiss = true;
      } else if (direction === 'right' && deltaX > threshold) {
        shouldDismiss = true;
      } else if (direction === 'left' && deltaX < -threshold) {
        shouldDismiss = true;
      } else if (direction === 'up' && deltaY < -threshold) {
        shouldDismiss = true;
      }

      if (shouldDismiss) {
        onDismiss();
      } else {
        // Reset position with animation
        element.style.transition = 'transform 0.2s ease-out, opacity 0.2s ease-out';
        element.style.transform = 'translate(0, 0)';
        element.style.opacity = '1';
        setTimeout(() => {
          element.style.transition = '';
        }, 200);
      }

      setIsSwiping(false);
    };

    element.addEventListener('touchstart', handleTouchStart, { passive: true });
    element.addEventListener('touchmove', handleTouchMove, { passive: true });
    element.addEventListener('touchend', handleTouchEnd);

    return () => {
      element.removeEventListener('touchstart', handleTouchStart);
      element.removeEventListener('touchmove', handleTouchMove);
      element.removeEventListener('touchend', handleTouchEnd);
    };
  }, [startPos, currentPos, isSwiping, threshold, direction, onDismiss]);

  return { ref, isSwiping };
};
