import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";

interface ScrollLinkProps {
  to: string;
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const ScrollLink = ({ to, children, className, onClick }: ScrollLinkProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    // Check if it's a hash link
    if (to.includes("#")) {
      e.preventDefault();
      
      const [path, hash] = to.split("#");
      const targetId = hash;
      
      // If we're already on the target page, just scroll
      if (location.pathname === path || (path === "/" && location.pathname === "/")) {
        const element = document.getElementById(targetId);
        if (element) {
          const offset = 80; // Account for fixed navbar height
          const elementPosition = element.getBoundingClientRect().top;
          const offsetPosition = elementPosition + window.pageYOffset - offset;
          
          window.scrollTo({
            top: offsetPosition,
            behavior: "smooth"
          });
        }
      } else {
        // Navigate to the page first, then scroll
        navigate(to);
      }
      
      onClick?.();
    } else {
      onClick?.();
    }
  };

  return (
    <Link to={to} className={className} onClick={handleClick}>
      {children}
    </Link>
  );
};

// Hook to handle scrolling on mount when hash is present
export const useHashScroll = () => {
  const location = useLocation();

  useEffect(() => {
    if (location.hash) {
      const id = location.hash.replace("#", "");
      setTimeout(() => {
        const element = document.getElementById(id);
        if (element) {
          const offset = 80; // Account for fixed navbar height
          const elementPosition = element.getBoundingClientRect().top;
          const offsetPosition = elementPosition + window.pageYOffset - offset;
          
          window.scrollTo({
            top: offsetPosition,
            behavior: "smooth"
          });
        }
      }, 100);
    }
  }, [location]);
};
