// Data Log 테이블과 관련 UI에서 공유하는 로그 타입 badge 스타일입니다.
const fallbackClass = "bg-muted text-foreground";

export const logTypeBadgeClasses = {
  EQP: "bg-primary/15 text-primary",
  TIP: "bg-accent/20 text-accent-foreground",
  SPC_ITL: "bg-primary/10 text-primary",
  FDC_ITL: "bg-destructive/10 text-destructive",
  RACB: "bg-destructive/10 text-destructive",
  CTTTM: "bg-secondary/20 text-foreground",
  ESOP: "bg-muted text-foreground",
};

export const getLogTypeBadgeClass = (logType) =>
  logTypeBadgeClasses[logType] || fallbackClass;
