const stats = [
  { value: "98.7%", label: "Uptime Reliability" },
  { value: "500+", label: "Active Traders" },
  { value: "$2M+", label: "Trading Volume" },
  { value: "24/7", label: "Market Monitoring" },
];

export const Stats = () => {
  return (
    <section className="py-16 bg-gradient-to-r from-primary/10 via-accent/10 to-primary/10 border-y border-border/50">
      <div className="container mx-auto px-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          {stats.map((stat, index) => (
            <div key={index} className="text-center">
              <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent mb-2">
                {stat.value}
              </div>
              <div className="text-muted-foreground font-medium">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
