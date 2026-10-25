const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    let errDetail = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      errDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail || errJson);
    } catch {
      // ignore json parse error
    }
    throw new Error(errDetail);
  }
  return res.json();
}

export const api = {
  getHealth: () => request<any>("/api/health"),
  getDbHealth: () => request<any>("/api/health/db"),
  getOverview: () => request<any>("/api/overview"),
  getGlobalMap: (params: { min_amount?: number; risk_filter?: string; days?: number }) => {
    const q = new URLSearchParams();
    if (params.min_amount !== undefined) q.set("min_amount", String(params.min_amount));
    if (params.risk_filter) q.set("risk_filter", params.risk_filter);
    if (params.days !== undefined) q.set("days", String(params.days));
    return request<any>(`/api/map/activity?${q.toString()}`);
  },
  getAccounts: (params: Record<string, any>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
    });
    return request<any>(`/api/accounts?${q.toString()}`);
  },
  getAccountDetail: (accountId: string) =>
    request<any>(`/api/accounts/${encodeURIComponent(accountId)}`),
  getAccountTransactions: (accountId: string, page = 1, direction = "all") =>
    request<any>(
      `/api/accounts/${encodeURIComponent(accountId)}/transactions?page=${page}&page_size=20&direction=${direction}`
    ),
  getTransactions: (params: Record<string, any>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
    });
    return request<any>(`/api/transactions?${q.toString()}`);
  },
  getTransactionDetail: (txId: string) =>
    request<any>(`/api/transactions/${encodeURIComponent(txId)}`),
  getAccountGraph: (
    accountId: string,
    params: {
      hops?: number;
      direction?: string;
      min_amount?: number;
      min_risk_score?: number;
      start_date?: string;
      end_date?: string;
    }
  ) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
    });
    return request<any>(`/api/graph/account/${encodeURIComponent(accountId)}?${q.toString()}`);
  },
  traceGraphPath: (payload: {
    source_account_id: string;
    target_account_id: string;
    max_hops?: number;
  }) =>
    request<any>("/api/graph/trace-path", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  explainAccount: (accountId: string) =>
    request<any>(`/api/explain/${encodeURIComponent(accountId)}`),
  runWhatIf: (payload: {
    account_id: string;
    feature_overrides: Record<string, number>;
    actor?: string;
  }) =>
    request<any>("/api/what-if", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAlerts: (params?: { status?: string; risk_category?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.risk_category) q.set("risk_category", params.risk_category);
    return request<any>(`/api/alerts?${q.toString()}`);
  },
  updateAlert: (
    alertId: string,
    payload: { status: string; assigned_to?: string; decision_notes?: string; actor?: string }
  ) =>
    request<any>(`/api/alerts/${encodeURIComponent(alertId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getInvestigations: (params?: { status?: string; account_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.account_id) q.set("account_id", params.account_id);
    return request<any>(`/api/investigations?${q.toString()}`);
  },
  createInvestigation: (payload: {
    account_id: string;
    title?: string;
    priority?: string;
    assigned_to?: string;
    initial_note?: string;
    actor?: string;
  }) =>
    request<any>("/api/investigations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getInvestigationDetail: (invId: string) =>
    request<any>(`/api/investigations/${encodeURIComponent(invId)}`),
  updateInvestigation: (invId: string, payload: Record<string, any>) =>
    request<any>(`/api/investigations/${encodeURIComponent(invId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  addInvestigationNote: (
    invId: string,
    payload: { author: string; note_type: string; content: string }
  ) =>
    request<any>(`/api/investigations/${encodeURIComponent(invId)}/notes`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  addInvestigationEvidence: (invId: string, payload: Record<string, any>) =>
    request<any>(`/api/investigations/${encodeURIComponent(invId)}/evidence`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getRiskAnalytics: (riskCategory?: string) =>
    request<any>(
      `/api/analytics/risk${riskCategory && riskCategory !== "all" ? `?risk_category=${riskCategory}` : ""}`
    ),
  getFinancialContext: () => request<any>("/api/context"),
  getAuditTrail: (params?: Record<string, string>) => {
    const q = new URLSearchParams(params || {});
    return request<any>(`/api/audit?${q.toString()}`);
  },
  getModels: () => request<any>("/api/models"),
  activateModel: (modelVersion: string) =>
    request<any>(`/api/models/${encodeURIComponent(modelVersion)}/activate`, {
      method: "POST",
    }),
  updateThresholds: (payload: {
    moderate: number;
    high: number;
    critical: number;
    updated_by: string;
  }) =>
    request<any>("/api/settings/thresholds?rescore=true", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  generateSyntheticData: (payload: Record<string, any>, background = true) =>
    request<any>(`/api/data/generate?background=${background}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  trainModel: (payload: Record<string, any>, background = true) =>
    request<any>(`/api/models/train?background=${background}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  validateImportDataset: (payload: Record<string, any>) =>
    request<any>("/api/data/validate-import", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getJobs: () => request<any>("/api/jobs"),
  getJob: (jobId: string) => request<any>(`/api/jobs/${encodeURIComponent(jobId)}`),
};

