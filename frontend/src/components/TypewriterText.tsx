import { useTypewriter } from "@/hooks/useTypewriter";

interface TypewriterTextProps {
  text: string;
  speed?: number;
  className?: string;
}

export function TypewriterText({ text, speed = 30, className }: TypewriterTextProps) {
  const displayedText = useTypewriter(text, speed);

  return <span className={className}>{displayedText}</span>;
}
