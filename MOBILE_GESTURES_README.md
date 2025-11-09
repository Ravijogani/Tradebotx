# Mobile Gestures & Animations Guide

## 🎨 Features Implemented

### 1. **Smooth Scroll Animations**
Landing page sections now animate smoothly as you scroll into view.

**How it works:**
- Sections fade in and slide up when they enter the viewport
- Uses Intersection Observer API for performance
- Respects user's motion preferences (`prefers-reduced-motion`)

**Customization:**
```typescript
// In any component
import { useScrollAnimation } from "@/hooks/useScrollAnimation";

const myAnimation = useScrollAnimation({ 
  threshold: 0.2,        // Trigger when 20% visible
  rootMargin: '0px',     // Offset from viewport
  triggerOnce: true      // Animate only once
});

<section ref={myAnimation.ref} className={`scroll-animate ${myAnimation.isVisible ? 'visible' : ''}`}>
  {/* Your content */}
</section>
```

### 2. **Pull-to-Refresh** (Dashboard)
Native mobile-style pull-to-refresh on the dashboard.

**How to use:**
- On mobile, swipe down from the top of the dashboard
- A refresh icon appears and rotates
- Release when the icon completes rotation
- Page refreshes automatically

**Customization:**
```typescript
import { usePullToRefresh } from "@/hooks/usePullToRefresh";

const pullToRefresh = usePullToRefresh({
  onRefresh: async () => {
    // Your refresh logic
    await fetchNewData();
  },
  threshold: 80,          // Distance to trigger (px)
  maxPullDistance: 150    // Maximum pull distance
});
```

### 3. **Swipe-to-Dismiss** (Modals)
Swipe down to close modal dialogs on mobile.

**How to use:**
Replace `Dialog` with `SwipeableDialog`:

```typescript
import { SwipeableDialog } from "@/components/ui/swipeable-dialog";
import { DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

<SwipeableDialog open={isOpen} onOpenChange={setIsOpen}>
  <DialogHeader>
    <DialogTitle>Your Title</DialogTitle>
    <DialogDescription>Your description</DialogDescription>
  </DialogHeader>
  {/* Your content */}
</SwipeableDialog>
```

**Features:**
- Visual indicator bar at the top (mobile only)
- Smooth drag animation
- Opacity changes as you swipe
- Snaps back if you don't swipe far enough
- Threshold: 100px swipe distance

### 4. **Enhanced Navigation**
Smooth scroll to anchor sections with proper offset for fixed navbar.

**Improvements:**
- `scroll-padding-top` accounts for fixed navbar height
- Smooth scroll behavior with CSS
- Works on all modern browsers

## 🎯 Animation Classes Available

### Basic Animations
- `.animate-fade-in` - Fade in with slight upward movement (0.6s)
- `.animate-fade-in-up` - Fade in with larger upward movement (0.8s)
- `.animate-slide-in-left` - Slide in from left (0.6s)
- `.animate-slide-in-right` - Slide in from right (0.6s)
- `.animate-scale-in` - Scale up with fade (0.4s)

### Scroll Animations
- `.scroll-animate` + `.visible` - Fade in and slide up on scroll

### Stagger Animations
- `.stagger-children` - Automatically staggers child animations
  - Each child gets a 0.1s delay increment
  - Up to 8 children supported

Example:
```html
<div class="stagger-children">
  <div>Item 1</div> <!-- Animates after 0.1s -->
  <div>Item 2</div> <!-- Animates after 0.2s -->
  <div>Item 3</div> <!-- Animates after 0.3s -->
</div>
```

## 📱 Mobile-First Considerations

### Touch Targets
All interactive elements maintain 44x44px minimum touch target size on mobile.

### Performance
- Animations use CSS transforms (GPU accelerated)
- Intersection Observer for scroll animations (no scroll listeners)
- Touch events use `passive: true` where possible
- Debounced scroll handlers

### Accessibility
- Respects `prefers-reduced-motion` media query
- Keyboard navigation still works on all components
- Screen reader announcements maintained

## 🛠️ Customization Guide

### Adjust Animation Timing
Edit `src/index.css`:
```css
@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(30px); /* Change distance */
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in-up {
  animation: fade-in-up 0.8s ease-out; /* Change duration/easing */
}
```

### Change Pull-to-Refresh Threshold
In `DashboardLayout.tsx`:
```typescript
const pullToRefresh = usePullToRefresh({
  onRefresh: handleRefresh,
  threshold: 120  // Increase to require longer pull
});
```

### Modify Swipe Direction
In any component using swipe:
```typescript
const { ref } = useSwipeToDismiss({
  onDismiss: handleClose,
  threshold: 100,
  direction: 'right' // Options: 'right', 'left', 'up', 'down'
});
```

## 🐛 Troubleshooting

**Animations not triggering:**
- Check if element has `.scroll-animate` class
- Verify `useScrollAnimation` hook is called
- Ensure element is actually scrolling into view

**Pull-to-refresh not working:**
- Must be at top of scroll container
- Only works on touch devices
- Check if `onRefresh` function is async

**Swipe-to-dismiss feels laggy:**
- Reduce threshold value for more sensitivity
- Check if other touch handlers are interfering
- Ensure `touch-action: pan-y` is not being overridden

## 🎨 Best Practices

1. **Use scroll animations sparingly** - Too many can feel overwhelming
2. **Keep pull-to-refresh threshold reasonable** - 80-120px works best
3. **Provide visual feedback** - Show loading states during refresh
4. **Test on real devices** - Touch gestures behave differently than mouse
5. **Consider accessibility** - Not all users can/want to use gestures

## 📊 Browser Support

- **Smooth Scroll**: All modern browsers (Chrome 61+, Safari 15.4+, Firefox 36+)
- **Intersection Observer**: All modern browsers (IE 11 with polyfill)
- **Touch Events**: All mobile browsers
- **CSS Animations**: All browsers

## 🚀 Future Enhancements

Potential additions:
- Swipe between pages/tabs
- Pinch-to-zoom on charts
- Long-press context menus
- Haptic feedback on supported devices
- More animation presets
