// Centralized log type badge styles for the data log table and related UI.
const fallbackClass = "bg-muted text-foreground";

export const logTypeBadgeClasses = {
  EQP: "bg-primary/15 text-primary",
  TIP: "bg-accent/20 text-accent-foreground",
  RACB: "bg-destructive/10 text-destructive",
  CTTTM: "bg-secondary/20 text-foreground",
  JIRA: "bg-muted text-foreground",
};

export const getLogTypeBadgeClass = (logType) =>
  logTypeBadgeClasses[logType] || fallbackClass;
