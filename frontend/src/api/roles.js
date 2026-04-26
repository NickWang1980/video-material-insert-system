import { api } from "./index";

export const listRoles = () => api.get("/roles");
export const createRole = (data) => api.post("/roles", data);
export const updateRole = (id, data) => api.patch(`/roles/${id}`, data);
export const deleteRole = (id) => api.delete(`/roles/${id}`);
