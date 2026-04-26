import { api } from "./index";

export async function listAuditLogs({ page = 1, pageSize = 20, entityType, operator, startDate, endDate } = {}) {
  const params = { page, page_size: pageSize };
  if (entityType) params.entity_type = entityType;
  if (operator) params.operator = operator;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const { data } = await api.get("/audit/logs", { params });
  return { items: data?.items || [], total: data?.total || 0 };
}

export async function fetchAllAuditLogs({ entityType, operator, startDate, endDate } = {}) {
  const params = { page: 1, page_size: 5000 };
  if (entityType) params.entity_type = entityType;
  if (operator) params.operator = operator;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const { data } = await api.get("/audit/logs", { params });
  return data?.items || [];
}

export async function clearAuditLogs() {
  const { data } = await api.delete("/audit/logs");
  return data;
}
